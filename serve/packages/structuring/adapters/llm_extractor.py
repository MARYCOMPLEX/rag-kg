"""LLM-based combined entity + relation extractor.

Sends a batch of chunks to the LLM with a schema-constrained prompt
asking for entities and triples. Provenance: every triple's evidence
references the chunk_id(s) it came from. Idempotent: extracting the
same chunks twice produces the same logical result (entity IDs are
content-derived).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.core.models import Chunk, Entity, Triple
from packages.llm.protocols import LLMClient, Message
from packages.structuring.schema import KGSchema, SchemaValidationError


class _LLMEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: str
    aliases: list[str] = Field(default_factory=list)  # type: ignore[arg-type]


class _LLMTriple(BaseModel):
    model_config = ConfigDict(extra="ignore")
    head: str
    head_type: str
    relation: str
    tail: str
    tail_type: str
    evidence_chunk_ids: list[str] = Field(default_factory=list)  # type: ignore[arg-type]
    confidence: float = 0.7


class _LLMExtractPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    entities: list[_LLMEntity] = Field(default_factory=list)  # type: ignore[arg-type]
    triples: list[_LLMTriple] = Field(default_factory=list)  # type: ignore[arg-type]


_SYSTEM_PROMPT = """You are a knowledge-graph extractor for academic papers.

Given a batch of TEXT CHUNKS, identify:
1. ENTITIES — named things that match the allowed entity types
2. TRIPLES — relations between entities, using ONLY the allowed relation types

Return strict JSON with this shape:
{{
  "entities": [
    {{"name": "GraphRAG", "type": "Method", "aliases": ["Graph-RAG"]}}
  ],
  "triples": [
    {{
      "head": "GraphRAG",
      "head_type": "Method",
      "relation": "improves_upon",
      "tail": "Naive RAG",
      "tail_type": "Method",
      "evidence_chunk_ids": ["doc::p1::3"],
      "confidence": 0.9
    }}
  ]
}}

Hard rules:
- ENTITY TYPES allowed: {entity_types}
- RELATION TYPES allowed: {relation_types}
- Every triple's head_type and tail_type must match one of the relation's allowed type pairs.
- Every triple MUST cite at least one chunk_id from the input as evidence.
- Skip triples you cannot ground in the chunks. Quality over quantity.
- Return ONLY JSON, no prose, no markdown fences."""

_USER_PROMPT_TEMPLATE = """CHUNKS:

{chunks}

Extract entities and triples now."""


@dataclass(frozen=True, slots=True)
class LLMExtractorConfig:
    """Tunables for the LLM extractor."""

    chunks_per_call: int = 5
    temperature: float = 0.0
    max_tokens: int = 2000
    timeout_s: float = 120.0
    max_concurrent: int = 4


@dataclass(frozen=True, slots=True)
class LLMExtractionResult:
    """Per-batch extraction output."""

    entities: tuple[Entity, ...] = ()
    triples: tuple[Triple, ...] = ()


class LLMEntityRelationExtractor:
    """Combined NER + RE in one LLM call per chunk batch.

    Doing both in one call cuts cost in half and lets the LLM ground
    triples in the same chunks it just enumerated entities from.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        schema: KGSchema,
        config: LLMExtractorConfig | None = None,
    ) -> None:
        self._llm = llm
        self._schema = schema
        self._config = config or LLMExtractorConfig()

    async def extract(self, library_id: str, chunks: list[Chunk]) -> LLMExtractionResult:
        """Extract entities + triples from chunks with bounded concurrency."""
        if not chunks:
            return LLMExtractionResult()

        batches = [
            chunks[i : i + self._config.chunks_per_call]
            for i in range(0, len(chunks), self._config.chunks_per_call)
        ]

        sem = asyncio.Semaphore(self._config.max_concurrent)

        async def _run(batch: list[Chunk]) -> LLMExtractionResult:
            async with sem:
                return await self._extract_batch(library_id, batch)

        results = await asyncio.gather(*(_run(b) for b in batches))

        all_entities: dict[str, Entity] = {}
        all_triples: list[Triple] = []
        for r in results:
            for e in r.entities:
                # Dedupe entities by entity_id; keep richer aliases when seen twice
                existing = all_entities.get(e.entity_id)
                if existing is None:
                    all_entities[e.entity_id] = e
                else:
                    merged_aliases = tuple(sorted(set(existing.aliases) | set(e.aliases)))
                    all_entities[e.entity_id] = existing.model_copy(
                        update={"aliases": merged_aliases}
                    )
            all_triples.extend(r.triples)

        return LLMExtractionResult(
            entities=tuple(all_entities.values()),
            triples=tuple(all_triples),
        )

    async def _extract_batch(self, library_id: str, batch: list[Chunk]) -> LLMExtractionResult:
        prompt = _SYSTEM_PROMPT.format(
            entity_types=", ".join(t.id for t in self._schema.entity_types),
            relation_types=", ".join(r.id for r in self._schema.relation_types),
        )
        chunk_text = "\n\n---\n\n".join(f"[chunk_id={c.chunk_id}]\n{c.text}" for c in batch)
        user = _USER_PROMPT_TEMPLATE.format(chunks=chunk_text)

        try:
            resp = await self._llm.complete(
                [
                    Message(role="system", content=prompt),
                    Message(role="user", content=user),
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout_s=self._config.timeout_s,
            )
        except Exception:
            # Single batch failure shouldn't fail the whole ingest
            return LLMExtractionResult()

        return self._parse_response(library_id, resp.text, batch)

    def _parse_response(
        self, library_id: str, text: str, batch: list[Chunk]
    ) -> LLMExtractionResult:
        json_text = _extract_json_block(text)
        if json_text is None:
            return LLMExtractionResult()
        try:
            payload = _LLMExtractPayload.model_validate_json(json_text)
        except (json.JSONDecodeError, ValidationError):
            return LLMExtractionResult()

        valid_chunk_ids = {c.chunk_id for c in batch}
        entities = self._parse_entities(library_id, payload.entities)
        triples = self._parse_triples(library_id, payload.triples, valid_chunk_ids)
        return LLMExtractionResult(entities=tuple(entities), triples=tuple(triples))

    def _parse_entities(self, library_id: str, items: list[_LLMEntity]) -> list[Entity]:
        out: list[Entity] = []
        for item in items:
            if not item.name or not item.type:
                continue
            if not self._schema.is_valid_entity_type(item.type):
                continue
            aliases = tuple(a.strip() for a in item.aliases if a.strip())
            out.append(
                Entity(
                    library_id=library_id,
                    entity_id=_canonical_entity_id(item.name, item.type),
                    name=item.name.strip(),
                    aliases=aliases,
                    type=item.type,
                )
            )
        return out

    def _parse_triples(
        self,
        library_id: str,
        items: list[_LLMTriple],
        valid_chunk_ids: set[str],
    ) -> list[Triple]:
        out: list[Triple] = []
        for item in items:
            if not all((item.head, item.tail, item.relation, item.head_type, item.tail_type)):
                continue
            try:
                self._schema.validate_triple(
                    relation=item.relation,
                    head_type=item.head_type,
                    tail_type=item.tail_type,
                )
            except SchemaValidationError:
                continue

            evidence = tuple(e for e in item.evidence_chunk_ids if e in valid_chunk_ids)
            if not evidence:
                continue

            confidence = max(0.0, min(1.0, item.confidence))

            out.append(
                Triple(
                    library_id=library_id,
                    head=_canonical_entity_id(item.head, item.head_type),
                    relation=item.relation,
                    tail=_canonical_entity_id(item.tail, item.tail_type),
                    evidence=evidence,
                    confidence=confidence,
                    source_model="llm",
                )
            )
        return out


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_block(text: str) -> str | None:
    """Best-effort: pull the largest balanced JSON object from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        # strip code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _canonical_entity_id(name: str, type_id: str) -> str:
    """Deterministic entity ID: type:slug(name) for cross-batch dedup."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]
    if not slug:
        slug = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"{type_id.lower()}:{slug}"
