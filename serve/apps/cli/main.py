"""rkb — CLI entry point for RAG-KG Copilot.

Global --library flag scopes all data operations to a single library.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from apps._shared.factories import AppContainer, build_container, ingest_pdf, rebuild_communities
from apps._shared.persistence.library_fs import make_library
from packages.core.backup import export_library, import_library
from packages.core.errors import (
    LibraryAlreadyExistsError,
    LibraryNotFoundError,
)
from packages.core.library_admin import init_library, purge_library
from packages.evaluation import (
    CitationF1Metric,
    CitationPresentMetric,
    DefaultEvalRunner,
    EvalRunnerConfig,
    FaithfulnessMetric,
    FilesystemSampleLoader,
    JSONFileRunsStore,
    KeyPointCoverageMetric,
    LatencyMetric,
    MarkdownReporter,
    Metric,
    MustNotContainMetric,
    RecallAtKMetric,
)
from packages.ingestion.idempotency import hash_file
from packages.ingestion.state import IngestStateStore

_SNIPPET_PREVIEW_LEN = 80

app = typer.Typer(
    name="rkb",
    help="RAG-KG Copilot CLI — manage libraries, ingest documents, ask questions.",
    no_args_is_help=True,
)
console = Console()

LibraryOption = Annotated[
    str | None,
    typer.Option("--library", "-l", envvar="RKB_LIBRARY", help="Target library ID"),
]


@app.command()
def version() -> None:
    """Show version."""
    console.print("rag-kg-copilot v0.1.0")


# ============================================================
# Library management
# ============================================================

library_app = typer.Typer(help="Manage libraries.", no_args_is_help=True)
app.add_typer(library_app, name="library")


@library_app.command("list")
def library_list() -> None:
    """List all libraries."""

    async def _run() -> None:
        container = build_container()
        try:
            libs = await container.library_repo.list_all()
        finally:
            await container.aclose()

        if not libs:
            console.print("[dim]No libraries yet. Create one with `rkb library create`.[/dim]")
            return

        table = Table(title="Libraries")
        for col in ["ID", "Name", "Description", "Created"]:
            table.add_column(col)
        for lib in libs:
            table.add_row(
                lib.library_id,
                lib.name,
                (lib.description or "")[:60],
                lib.created_at.isoformat(timespec="minutes"),
            )
        console.print(table)

    asyncio.run(_run())


@library_app.command("create")
def library_create(
    library_id: str = typer.Argument(help="Library slug (lowercase, 3-31 chars)"),
    name: str = typer.Option("", "--name", help="Human-readable name"),
    description: str = typer.Option("", "--description", help="Description"),
) -> None:
    """Create a new library — registers metadata + initializes all index backends."""

    async def _run() -> None:
        container = build_container(library_id_for_schema=library_id)
        try:
            try:
                lib = make_library(
                    library_id=library_id,
                    name=name or library_id,
                    description=description or None,
                )
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(code=1) from e

            try:
                await container.library_repo.create(lib)
            except LibraryAlreadyExistsError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(code=1) from e

            await init_library(
                library_id,
                adapters=[
                    container.vector_index,
                    container.bm25_index,
                    container.graph_index,
                    container.community_index,
                ],
            )
            console.print(f"[green]Created library:[/green] {library_id} ({name or library_id})")
            console.print(f"  data dir: data/libraries/{library_id}/")
            console.print(f"  qdrant collection: chunks_{library_id.replace('-', '_')}")
            console.print(f"  bm25 index: bm25_{library_id.replace('-', '_')}")
            console.print(f"  neo4j label: Lib_{library_id.replace('-', '_')}")
            console.print(f"  community collection: communities_{library_id.replace('-', '_')}")
        finally:
            await container.aclose()

    asyncio.run(_run())


@library_app.command("purge")
def library_purge(
    library_id: str = typer.Argument(help="Library to purge"),
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually purge"),
) -> None:
    """Purge a library — removes meta, files, vector, BM25, AND KG."""
    if not confirm:
        console.print("[red]Pass --confirm to actually purge.[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            try:
                await purge_library(
                    library_id,
                    adapters=[
                        container.vector_index,
                        container.bm25_index,
                        container.graph_index,
                        container.community_index,
                    ],
                )
                await container.library_repo.delete(library_id)
            except LibraryNotFoundError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(code=1) from e
            console.print(f"[green]Purged library:[/green] {library_id}")
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# Ingest
# ============================================================


def _report_ingest_plan(
    container: AppContainer, library: str, pdfs: list[Path], *, force: bool
) -> None:
    """Print [skipped|would-ingest] for each PDF without doing any work."""
    state_dir = Path(container.settings.ingest_state_dir)
    store = IngestStateStore(state_dir / "ingest.sqlite")
    try:
        for pdf in pdfs:
            sha = hash_file(pdf)
            prior = store.get(library, sha)
            status = "skipped" if prior and prior.status == "done" and not force else "would-ingest"
            console.print(f"  [{status}]  {pdf.name}")
    finally:
        store.close()


@app.command()
def ingest(
    path: str = typer.Argument(help="Path to PDF file or directory of PDFs"),
    library: LibraryOption = None,
    force: bool = typer.Option(
        False, "--force", help="Re-ingest even if the file's SHA-256 was previously processed"
    ),
    report_only: bool = typer.Option(
        False, "--report-only", help="Print what would be done without running the pipeline"
    ),
) -> None:
    """Ingest one or more PDFs into a library.

    Idempotent by default: files whose SHA-256 already has status=done are
    skipped. Pass --force to override (e.g., after a parser/embedder change).
    """
    if not library:
        console.print("[red]--library is required (or set RKB_LIBRARY env var)[/red]")
        raise typer.Exit(code=1)

    p = Path(path)
    if not p.exists():
        console.print(f"[red]Path not found: {p}[/red]")
        raise typer.Exit(code=1)

    pdfs = sorted(p.glob("**/*.pdf")) if p.is_dir() else [p]
    if not pdfs:
        console.print(f"[yellow]No PDFs found at {p}[/yellow]")
        raise typer.Exit(code=0)

    async def _run() -> None:
        container = build_container(library_id_for_schema=library)
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist. Create it first.[/red]")
                raise typer.Exit(code=1)
            await init_library(
                library,
                adapters=[
                    container.vector_index,
                    container.bm25_index,
                    container.graph_index,
                    container.community_index,
                ],
            )

            extract_kg = container.extractor is not None
            if not extract_kg:
                console.print(
                    "[yellow]No KG schema for this library — skipping KG extraction.[/yellow]"
                )

            if report_only:
                _report_ingest_plan(container, library, pdfs, force=force)
                return

            total_chunks = 0
            total_entities = 0
            total_triples = 0
            skipped = 0
            for pdf in pdfs:
                console.print(f"[cyan]Ingesting:[/cyan] {pdf.name}")
                result = await ingest_pdf(
                    container,
                    library_id=library,
                    pdf_path=pdf,
                    extract_kg=extract_kg,
                    force=force,
                )
                if result.skipped:
                    console.print(f"  [dim]→ skipped (already ingested as {result.doc_id})[/dim]")
                    skipped += 1
                else:
                    console.print(
                        f"  → {result.title[:60]}: "
                        f"{result.chunks_created} chunks, "
                        f"{result.entities_extracted} entities, "
                        f"{result.triples_extracted} triples"
                    )
                total_chunks += result.chunks_upserted
                total_entities += result.entities_extracted
                total_triples += result.triples_extracted

            cached, size_b = await container.embedder.cache_stats()
            kg_total = await container.graph_index.count_triples(library)
            console.print(
                f"\n[green]Done.[/green] {len(pdfs)} files "
                f"({skipped} skipped), "
                f"{total_chunks} chunks, "
                f"{total_entities} entities, "
                f"{total_triples} triples (KG total: {kg_total}). "
                f"Cache: {cached} entries ({size_b // 1024} KB)"
            )
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# Entity neighborhood (KG exploration)
# ============================================================


@library_app.command("neighborhood")
def library_neighborhood(
    entity_id: str = typer.Argument(help="Entity ID (e.g., 'method:graphrag')"),
    depth: int = typer.Option(1, help="Hops to expand (1-3)"),
    library: LibraryOption = None,
) -> None:
    """Show triples within N hops of an entity in a library's KG."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            triples = await container.graph_index.get_neighbors(library, entity_id, depth=depth)
            if not triples:
                console.print(f"[yellow]No neighbors for '{entity_id}' in '{library}'.[/yellow]")
                return
            table = Table(title=f"Neighborhood of {entity_id} (depth={depth})")
            for col in ["Head", "Relation", "Tail", "Confidence", "Evidence"]:
                table.add_column(col)
            for t in triples:
                table.add_row(
                    t.head,
                    t.relation,
                    t.tail,
                    f"{t.confidence:.2f}",
                    str(len(t.evidence)),
                )
            console.print(table)
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# Community rebuild (M3)
# ============================================================


@library_app.command("rebuild-community")
def library_rebuild_community(
    library: LibraryOption = None,
) -> None:
    """Detect KG communities, summarize them, and index for global search."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container(library_id_for_schema=library)
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)

            console.print(f"[cyan]Rebuilding communities for {library}...[/cyan]")
            result = await rebuild_communities(container, library_id=library)

            table = Table(title=f"Community rebuild — {library}")
            table.add_column("Metric")
            table.add_column("Value")
            table.add_row("Triples loaded", str(result.triples_loaded))
            table.add_row("Communities detected", str(result.communities_detected))
            table.add_row("Communities summarized", str(result.communities_summarized))
            table.add_row("Communities indexed", str(result.communities_indexed))
            console.print(table)
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# QA
# ============================================================


@app.command()
def qa(
    question: str = typer.Argument(help="Your question"),
    library: LibraryOption = None,
) -> None:
    """Ask a question against a library."""
    if not library:
        console.print("[red]--library is required (or set RKB_LIBRARY env var)[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)

            answer = await container.qa_task.answer(library, question)

            console.print(f"\n[bold cyan]Q:[/bold cyan] {question}\n")
            console.print(f"[bold green]A:[/bold green] {answer.answer}\n")

            if answer.citations:
                table = Table(title=f"Citations ({len(answer.citations)})")
                for col in ["Chunk ID", "Doc", "Page", "Snippet"]:
                    table.add_column(col)
                for cit in answer.citations:
                    table.add_row(
                        cit.chunk_id,
                        cit.doc_id,
                        str(cit.page or "-"),
                        cit.snippet[:_SNIPPET_PREVIEW_LEN]
                        + ("…" if len(cit.snippet) > _SNIPPET_PREVIEW_LEN else ""),
                    )
                console.print(table)
            else:
                console.print("[yellow]No citations extracted.[/yellow]")

            console.print(
                f"\n[dim]model={answer.model}  "
                f"tokens=in:{answer.tokens.input_tokens}/out:{answer.tokens.output_tokens}  "
                f"latency={answer.duration_ms}ms[/dim]"
            )
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# M5 research tasks
# ============================================================


@app.command()
def review(
    topic: str = typer.Argument(help="Topic for the literature review"),
    library: LibraryOption = None,
) -> None:
    """Generate a literature review on a topic from the library."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)
            console.print(f"[cyan]Generating review on:[/cyan] {topic}\n")
            result = await container.review_task.run(library, topic)
            if result.abstract:
                console.print(f"[bold]Abstract:[/bold] {result.abstract}\n")
            for sec in result.sections:
                console.print(f"[bold cyan]## {sec.heading}[/bold cyan]")
                console.print(f"{sec.body}\n")
            console.print(
                f"[dim]{len(result.sections)} sections, "
                f"{result.cost.llm_calls} LLM calls, "
                f"{result.cost.input_tokens}+{result.cost.output_tokens} tokens, "
                f"{result.cost.duration_ms}ms[/dim]"
            )
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def reason(
    question: str = typer.Argument(help="Multi-hop research question"),
    library: LibraryOption = None,
) -> None:
    """Cross-paper reasoning: decompose, retrieve, aggregate."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)
            console.print(f"[bold cyan]Q:[/bold cyan] {question}\n")
            result = await container.reasoning_task.run(library, question)
            for i, step in enumerate(result.sub_steps, 1):
                console.print(f"[dim]{i}.[/dim] [yellow]{step.sub_question}[/yellow]")
                console.print(f"   {step.answer}\n")
            console.print(f"[bold green]Final:[/bold green] {result.final_answer}\n")
            console.print(
                f"[dim]{len(result.sub_steps)} sub-steps, "
                f"{len(result.citations)} citations, "
                f"{result.cost.llm_calls} LLM calls, "
                f"{result.cost.duration_ms}ms[/dim]"
            )
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def hypothesize(
    head: str = typer.Argument(help="Head entity_id (e.g., 'method:hipporag')"),
    tail: str = typer.Argument(help="Tail entity_id (e.g., 'method:graphrag')"),
    library: LibraryOption = None,
) -> None:
    """Generate hypotheses connecting two KG entities."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)
            console.print(f"[cyan]Hypothesizing {head} ↔ {tail}[/cyan]\n")
            result = await container.hypothesis_task.run(library, head, tail)
            for i, hyp in enumerate(result.hypotheses, 1):
                console.print(f"[bold]{i}. {hyp.statement}[/bold]")
                console.print(f"   [dim]rationale:[/dim] {hyp.rationale}")
                console.print(f"   [dim]confidence:[/dim] {hyp.confidence:.2f}")
                if hyp.counter_evidence:
                    console.print(f"   [dim]counter:[/dim] {hyp.counter_evidence}")
                console.print(f"   [dim]paths: {len(hyp.supporting_paths)}[/dim]\n")
            console.print(
                f"[dim]{result.cost.llm_calls} LLM calls, {result.cost.duration_ms}ms[/dim]"
            )
        finally:
            await container.aclose()

    asyncio.run(_run())


# ============================================================
# Eval (M6)
# ============================================================


@app.command(name="eval")
def eval_cmd(
    suite: str = typer.Option("qa.smoke", "--suite", help="Eval suite name"),
    version: str = typer.Option("v1", "--version", help="Suite version"),
    library: LibraryOption = None,
    judge: bool = typer.Option(True, "--judge/--no-judge", help="Enable LLM-judge metrics"),
    save: bool = typer.Option(True, "--save/--no-save", help="Persist run to disk"),
) -> None:
    """Run an evaluation suite against a library and print a markdown report."""
    if not library:
        console.print("[red]--library is required[/red]")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container(library_id_for_schema=library)
        try:
            if not await container.library_repo.exists(library):
                console.print(f"[red]Library '{library}' does not exist.[/red]")
                raise typer.Exit(code=1)

            metrics: list[Metric] = [
                RecallAtKMetric(),
                KeyPointCoverageMetric(),
                CitationPresentMetric(),
                MustNotContainMetric(),
                LatencyMetric(),
            ]
            if judge:
                judge_model = container.settings.llm_model
                metrics.extend(
                    [
                        CitationF1Metric(llm=container.llm, judge_model=judge_model),
                        FaithfulnessMetric(llm=container.llm, judge_model=judge_model),
                    ]
                )

            data_dir = Path(container.settings.data_dir)
            loader = FilesystemSampleLoader(data_dir=data_dir)
            runner = DefaultEvalRunner(
                qa_task=container.qa_task,
                loader=loader,
                metrics=metrics,
                config=EvalRunnerConfig(parallelism=4, llm_judge_enabled=judge),
            )

            console.print(f"[cyan]Running {suite}@{version} on {library}...[/cyan]")
            run = await runner.run_suite(library, suite, version)

            reporter = MarkdownReporter()
            console.print(reporter.render_summary(run))

            if save:
                store = JSONFileRunsStore(data_dir=data_dir)
                path = await store.save(run)
                console.print(f"\n[dim]Saved to {path}[/dim]")
        finally:
            await container.aclose()

    asyncio.run(_run())


@library_app.command("export")
def library_export(
    library_id: str = typer.Argument(help="Library to export"),
    out_dir: Path = typer.Option(
        Path("data/backups"), "--out", help="Directory to write the archive into"
    ),
) -> None:
    """Export Library meta + corpus + KG + community summaries to a tar.gz archive."""

    async def _run() -> None:
        container = build_container()
        try:
            report = await export_library(
                library_id=library_id,
                out_dir=out_dir,
                library_repo=container.library_repo,
                vector_index=container.vector_index,
                graph_index=container.graph_index,
                community_index=container.community_index,
                state_store=None,
                libraries_root=Path(container.settings.data_dir) / "libraries",
            )
        finally:
            await container.aclose()

        console.print(
            f"[green]Exported[/green] {report.library_id} → {report.archive_path}\n"
            f"  documents={report.documents} chunks={report.chunks} "
            f"triples={report.triples} communities={report.communities}"
        )
        if report.notes:
            console.print("[yellow]Notes:[/yellow]")
            for n in report.notes:
                console.print(f"  - {n}")

    asyncio.run(_run())


@library_app.command("import")
def library_import(
    archive: Path = typer.Argument(help="Path to a previously exported .tar.gz archive"),
    target_id: str = typer.Option(..., "--as", help="Library ID to restore the archive as"),
) -> None:
    """Restore a library archive (meta + corpus). Re-run `rkb ingest` after this."""

    async def _run() -> None:
        container = build_container()
        try:
            result = await import_library(
                archive_path=archive,
                target_library_id=target_id,
                library_repo=container.library_repo,
                libraries_root=Path(container.settings.data_dir) / "libraries",
            )
        finally:
            await container.aclose()
        console.print(f"[green]Restored[/green] library {target_id}: {result}")

    asyncio.run(_run())


def main() -> None:
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
