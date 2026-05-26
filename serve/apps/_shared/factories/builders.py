"""DI container assembly.

Wires Settings → adapters → planner → QATask. Keeps construction in
one place so apps stay dumb.

M2: Neo4j KG, OpenSearch BM25, SiliconFlow reranker, hybrid retrieval, KG extractor.
M3: Community detector + summarizer + Qdrant community index, local/global routing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from apps._shared.factories.minio_presign import MinioPresigner, build_minio_presigner
from apps._shared.persistence import FilesystemLibraryRepository
from packages.context.budget import CharCountTokenCounter
from packages.context.compactor import TurnCompactor
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget
from packages.context.query_rewriter import QueryRewriter
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.embedding.adapters.cached import CachedEmbedder
from packages.embedding.adapters.openai_compat import (
    OpenAICompatEmbedder,
    OpenAICompatEmbedderConfig,
)
from packages.embedding.adapters.openai_compat_rerank import (
    OpenAICompatReranker,
    OpenAICompatRerankerConfig,
)
from packages.indexing.adapters.community_leiden import (
    LeidenCommunityDetector,
    LeidenCommunityDetectorConfig,
)
from packages.indexing.adapters.neo4j_graph import (
    Neo4jGraphIndex,
    Neo4jGraphIndexConfig,
)
from packages.indexing.adapters.opensearch_bm25 import (
    OpenSearchBM25Config,
    OpenSearchBM25Index,
)
from packages.indexing.adapters.qdrant_community import (
    QdrantCommunityIndex,
    QdrantCommunityIndexConfig,
)
from packages.indexing.adapters.qdrant_vector import (
    QdrantVectorIndex,
    QdrantVectorIndexConfig,
)
from packages.indexing.service import HybridRetrievalConfig, HybridRetrievalCoordinator
from packages.ingestion.adapters.pypdf_parser import PypdfParser
from packages.ingestion.adapters.sentence_chunker import SentenceChunker
from packages.llm.adapters.openai_compat import OpenAICompatLLM, OpenAICompatLLMConfig
from packages.llm.protocols import LLMClient
from packages.observability import (
    LangfuseConfig,
    LangfuseTracedLLM,
    TracingConfig,
    setup_tracing,
)
from packages.orchestration.tasks.hypothesis_task import HypothesisTask
from packages.orchestration.tasks.qa_task import QATask
from packages.orchestration.tasks.reasoning_task import CrossPaperReasoningTask
from packages.orchestration.tasks.review_task import ReviewGenerationTask
from packages.retrieval.protocols import RetrievalBudget, RetrievalPlanner
from packages.retrieval.router import QueryRouter
from packages.retrieval.strategies.coordinator_rag import CoordinatorRAGPlanner
from packages.retrieval.strategies.direct_rag import DirectRAGPlanner
from packages.retrieval.strategies.global_rag import GlobalRAGPlanner
from packages.retrieval.strategies.react_rag import ReActPlanner, ReActPlannerConfig
from packages.retrieval.strategies.routed_rag import RoutedRAGPlanner
from packages.structuring.adapters.llm_community_summarizer import (
    LLMCommunitySummarizer,
    LLMCommunitySummarizerConfig,
)
from packages.structuring.adapters.llm_extractor import (
    LLMEntityRelationExtractor,
    LLMExtractorConfig,
)
from packages.structuring.adapters.string_linker import StringEntityLinker
from packages.structuring.schema import KGSchema, load_schema


@dataclass(frozen=True, slots=True)
class AppContainer:
    """All wired dependencies, ready for use by CLI/API/Worker."""

    settings: Settings
    library_repo: FilesystemLibraryRepository
    parser: PypdfParser
    chunker: SentenceChunker
    embedder: CachedEmbedder
    raw_embedder: OpenAICompatEmbedder
    vector_index: QdrantVectorIndex
    bm25_index: OpenSearchBM25Index
    graph_index: Neo4jGraphIndex
    community_index: QdrantCommunityIndex
    reranker: OpenAICompatReranker
    raw_llm: OpenAICompatLLM
    llm: LLMClient
    planner: RetrievalPlanner
    qa_task: QATask
    review_task: ReviewGenerationTask
    reasoning_task: CrossPaperReasoningTask
    hypothesis_task: HypothesisTask
    schema: KGSchema | None
    extractor: LLMEntityRelationExtractor | None
    linker: StringEntityLinker
    community_detector: LeidenCommunityDetector
    community_summarizer: LLMCommunitySummarizer
    router: QueryRouter
    # M8: context management
    conversation_repo: SqliteConversationRepo
    memory_store: SqliteMemoryStore
    research_memory: ResearchMemory
    context_service: ContextService
    query_rewriter: QueryRewriter
    prompt_composer: PromptComposer
    turn_compactor: TurnCompactor
    context_budget: ContextBudget
    # ADR_REVIEW §11.3 — real MinIO presigned-GET adapter; the route uses
    # `getattr(container, "minio_presign_get", None)` so this can stay
    # `None` in unit tests / cold-start environments. Defaulted to `None`
    # so existing test factories that omit the field keep compiling.
    minio_presigner: MinioPresigner | None = None
    minio_presign_get: Callable[..., Awaitable[str]] | None = None

    async def aclose(self) -> None:
        """Close all underlying network clients.

        Closes the wrapper `llm` first so trace exporters (e.g., Langfuse)
        can flush before the underlying httpx client is torn down. The
        wrapper itself delegates to `raw_llm.close()`, so only one of them
        is closed in the wrapped case.
        """
        await self.raw_embedder.close()
        llm_close = getattr(self.llm, "close", None)
        if llm_close is not None:
            await llm_close()
        elif self.llm is not self.raw_llm:
            await self.raw_llm.close()
        await self.vector_index.close()
        await self.bm25_index.close()
        await self.graph_index.close()
        await self.reranker.close()
        await self.community_index.close()
        # M8 context stores share a single sqlite file; ContextService
        # cascades close to both the conversation repo and memory store.
        await self.context_service.aclose()


def _try_load_schema(library_id: str | None) -> KGSchema | None:
    """Load schema for a library if one exists; otherwise None."""
    if not library_id:
        return None
    ontology_dir = Path("docs/ontology")
    try:
        return load_schema(library_id, ontology_dir)
    except FileNotFoundError:
        return None


@dataclass(frozen=True, slots=True)
class _ContextBundle:
    """All context-management deps assembled together — keeps build_container small."""

    conversation_repo: SqliteConversationRepo
    memory_store: SqliteMemoryStore
    research_memory: ResearchMemory
    context_service: ContextService
    query_rewriter: QueryRewriter
    prompt_composer: PromptComposer
    turn_compactor: TurnCompactor
    context_budget: ContextBudget


def _build_context(s: Settings, llm: LLMClient) -> _ContextBundle:
    """Wire the M8 context-management subsystem from Settings + shared LLM."""
    context_db_path = Path(s.context_db_path)
    conversation_repo = SqliteConversationRepo(context_db_path)
    memory_store = SqliteMemoryStore(context_db_path)
    research_memory = ResearchMemory(
        store=memory_store,
        max_entries_in_prompt=s.context_memory_max_entries_in_prompt,
    )
    context_service = ContextService(store=conversation_repo, memory_store=memory_store)
    query_rewriter = QueryRewriter(
        llm=llm,
        min_confidence=s.rewrite_min_confidence,
        max_tokens_out=s.rewrite_max_tokens_out,
        timeout_s=float(s.llm_timeout_s),
    )
    token_counter = CharCountTokenCounter()
    prompt_composer = PromptComposer(counter=token_counter)
    context_budget = ContextBudget(max_input_tokens=s.context_max_input_tokens)
    turn_compactor = TurnCompactor(
        llm=llm,
        counter=token_counter,
        budget=context_budget,
        summary_max_tokens=s.context_compact_summary_max_tokens,
        llm_timeout_s=float(s.llm_timeout_s),
    )
    return _ContextBundle(
        conversation_repo=conversation_repo,
        memory_store=memory_store,
        research_memory=research_memory,
        context_service=context_service,
        query_rewriter=query_rewriter,
        prompt_composer=prompt_composer,
        turn_compactor=turn_compactor,
        context_budget=context_budget,
    )


def _build_llm(s: Settings) -> tuple[OpenAICompatLLM, LLMClient]:
    """Build the raw LLM and (optionally) wrap it with Langfuse tracing."""
    raw_llm = OpenAICompatLLM(
        OpenAICompatLLMConfig(
            api_base=s.llm_api_base,
            api_key=s.llm_api_key,
            model=s.llm_model,
            timeout_s=s.llm_timeout_s,
        )
    )
    if not s.langfuse_enabled:
        return raw_llm, raw_llm
    wrapped: LLMClient = LangfuseTracedLLM(
        inner=raw_llm,
        config=LangfuseConfig(
            enabled=True,
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        ),
        default_tags=[f"service:{s.otel_service_name}"],
    )
    return raw_llm, wrapped


def _build_minio(
    s: Settings,
) -> tuple[MinioPresigner | None, Callable[..., Awaitable[str]] | None]:
    """Build the MinIO presigner pair (instance + bound method) from Settings.

    The ``Minio`` client constructor performs no I/O (TCP only on the
    first request), so it is safe to build at container assembly time.
    The API route falls back to a deterministic placeholder URL when
    this returns ``(None, None)`` — e.g. unit tests with no MinIO
    endpoint configured. (ADR_REVIEW §11.3.)
    """
    if not s.minio_endpoint:
        return None, None
    presigner = build_minio_presigner(s)
    return presigner, presigner.presign_get


def build_container(
    settings: Settings | None = None,
    *,
    library_id_for_schema: str | None = None,
) -> AppContainer:
    """Build the full DI graph from Settings."""
    s = settings or Settings()
    data_dir = Path(s.data_dir)

    library_repo = FilesystemLibraryRepository(data_dir=data_dir)

    raw_embedder = OpenAICompatEmbedder(
        OpenAICompatEmbedderConfig(
            api_base=s.embedding_api_base,
            api_key=s.embedding_api_key,
            model=s.embedding_model,
            dim=s.embedding_dim,
            batch_size=s.embedding_batch_size,
            timeout_s=s.embedding_timeout_s,
        )
    )
    cache_path = data_dir / "cache" / "embeddings.sqlite"
    embedder = CachedEmbedder(
        inner=raw_embedder,
        cache_path=cache_path,
        model_id=s.embedding_model,
    )

    vector_index = QdrantVectorIndex(
        QdrantVectorIndexConfig(
            url=s.qdrant_url,
            dim=s.embedding_dim,
            distance="Cosine",
        )
    )
    bm25_index = OpenSearchBM25Index(OpenSearchBM25Config(url=s.opensearch_url))
    graph_index = Neo4jGraphIndex(
        Neo4jGraphIndexConfig(
            uri=s.neo4j_uri,
            user=s.neo4j_user,
            password=s.neo4j_password,
        )
    )
    community_index = QdrantCommunityIndex(
        QdrantCommunityIndexConfig(
            url=s.qdrant_url,
            dim=s.embedding_dim,
            distance="Cosine",
        )
    )

    reranker = OpenAICompatReranker(
        OpenAICompatRerankerConfig(
            api_base=s.rerank_api_base,
            api_key=s.rerank_api_key,
            model=s.rerank_model,
            timeout_s=s.rerank_timeout_s,
        )
    )

    # ----- Observability bootstrap (idempotent) -----
    setup_tracing(
        TracingConfig(
            enabled=s.otel_enabled,
            service_name=s.otel_service_name,
            otlp_endpoint=s.otel_otlp_endpoint,
            sample_rate=s.otel_sample_rate,
        )
    )

    raw_llm, llm = _build_llm(s)

    # ----- Local planner (vector or hybrid) -----
    local_planner: RetrievalPlanner
    if s.hybrid_enabled:
        coordinator = HybridRetrievalCoordinator(
            embedder=embedder,
            vector=vector_index,
            bm25=bm25_index,
            reranker=reranker if s.rerank_enabled else None,
            config=HybridRetrievalConfig(
                k_vector=s.hybrid_k_vector,
                k_bm25=s.hybrid_k_bm25,
                rrf_k=s.hybrid_rrf_k,
                k_final=s.hybrid_k_final,
                rerank=s.rerank_enabled,
            ),
        )
        local_planner = CoordinatorRAGPlanner(coordinator=coordinator, source="hybrid")
    else:
        local_planner = DirectRAGPlanner(embedder=embedder, vector_index=vector_index)

    # ----- Global planner (community summaries) -----
    global_planner = GlobalRAGPlanner(
        embedder=embedder,
        community_index=community_index,
        k=s.global_search_k,
    )

    # ----- Router-driven planner (M3 default: chooses local vs global) -----
    router = QueryRouter()
    routed_planner = (
        RoutedRAGPlanner(
            router=router,
            local_planner=local_planner,
            global_planner=global_planner,
        )
        if s.community_enabled
        else local_planner
    )

    # ----- ReAct planner (M4 agentic) -----
    react_planner = ReActPlanner(
        llm=llm,
        embedder=embedder,
        vector_index=vector_index,
        bm25_index=bm25_index,
        graph_index=graph_index,
        budget=RetrievalBudget(
            max_steps=s.react_max_steps,
            max_llm_calls=s.react_max_llm_calls,
            max_input_tokens=s.react_max_input_tokens,
            max_output_tokens=s.react_max_output_tokens,
            timeout_s=s.react_timeout_s,
        ),
        config=ReActPlannerConfig(
            vector_k=s.react_vector_k,
            bm25_k=s.react_bm25_k,
            kg_depth=s.react_kg_depth,
        ),
    )

    # ----- Choose final planner via config -----
    planner_choice = s.planner.lower()
    planner: RetrievalPlanner
    if planner_choice == "direct":
        planner = DirectRAGPlanner(embedder=embedder, vector_index=vector_index)
    elif planner_choice == "hybrid":
        planner = local_planner
    elif planner_choice == "global":
        planner = global_planner
    elif planner_choice == "react":
        planner = react_planner
    else:  # "routed" (M3 default) and any unknown value
        planner = routed_planner

    qa_task = QATask(
        planner=planner,
        llm=llm,
        max_context_chunks=s.hybrid_k_final,
        llm_timeout_s=float(s.llm_timeout_s),
    )

    # ----- M8: Context management -----
    ctx = _build_context(s, llm)

    # ----- M5 research tasks -----
    review_task = ReviewGenerationTask(planner=planner, llm=llm)
    reasoning_task = CrossPaperReasoningTask(planner=planner, llm=llm)
    hypothesis_task = HypothesisTask(graph_index=graph_index, llm=llm)

    schema = _try_load_schema(library_id_for_schema)
    extractor: LLMEntityRelationExtractor | None = None
    if schema is not None and s.kg_enabled:
        extractor = LLMEntityRelationExtractor(
            llm=llm,
            schema=schema,
            config=LLMExtractorConfig(
                chunks_per_call=s.kg_chunks_per_call,
                max_concurrent=s.kg_max_concurrent,
                timeout_s=float(s.llm_timeout_s),
            ),
        )

    community_detector = LeidenCommunityDetector(
        LeidenCommunityDetectorConfig(
            random_seed=s.community_random_seed,
            min_community_size=s.community_min_size,
            max_levels=s.community_max_levels,
        )
    )
    community_summarizer = LLMCommunitySummarizer(
        llm=llm,
        model_name=s.llm_model,
        config=LLMCommunitySummarizerConfig(
            max_entities_in_prompt=s.community_summary_max_entities,
            max_triples_in_prompt=s.community_summary_max_triples,
            timeout_s=float(s.llm_timeout_s),
        ),
    )

    minio_presigner, minio_presign_get = _build_minio(s)

    return AppContainer(
        settings=s,
        library_repo=library_repo,
        parser=PypdfParser(),
        chunker=SentenceChunker(),
        embedder=embedder,
        raw_embedder=raw_embedder,
        vector_index=vector_index,
        bm25_index=bm25_index,
        graph_index=graph_index,
        community_index=community_index,
        reranker=reranker,
        raw_llm=raw_llm,
        llm=llm,
        planner=planner,
        qa_task=qa_task,
        review_task=review_task,
        reasoning_task=reasoning_task,
        hypothesis_task=hypothesis_task,
        schema=schema,
        extractor=extractor,
        linker=StringEntityLinker(),
        community_detector=community_detector,
        community_summarizer=community_summarizer,
        router=router,
        conversation_repo=ctx.conversation_repo,
        memory_store=ctx.memory_store,
        research_memory=ctx.research_memory,
        context_service=ctx.context_service,
        query_rewriter=ctx.query_rewriter,
        prompt_composer=ctx.prompt_composer,
        turn_compactor=ctx.turn_compactor,
        context_budget=ctx.context_budget,
        minio_presigner=minio_presigner,
        minio_presign_get=minio_presign_get,
    )
