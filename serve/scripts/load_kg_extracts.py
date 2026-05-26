"""Load Claude-extracted KG JSONs into Neo4j.

Reads `data/libraries/<lib>/kg_extracts/*.json`, validates against the
library schema, dedupes entities globally (by canonical entity_id),
and writes everything to Neo4j via the existing GraphIndex adapter.

Usage:
    uv run python scripts/load_kg_extracts.py --library rag-agent
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from apps._shared.factories import build_container
from packages.core.models import Entity, Triple
from packages.structuring.schema import KGSchema, SchemaValidationError, load_schema

console = Console()


def _canonical_entity_id(name: str, type_id: str) -> str:
    """Deterministic ID matching the LLM extractor's convention."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]
    if not slug:
        slug = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"{type_id.lower()}:{slug}"


def _validate_and_collect(
    extracts_dir: Path,
    library_id: str,
    schema: KGSchema,
) -> tuple[list[Entity], list[Triple], dict[str, dict[str, int]]]:
    """Read every JSON file, validate against schema, return entities + triples.

    Returns (entities, triples, per_doc_stats).
    """
    entities_by_id: dict[str, Entity] = {}
    triples_set: set[tuple[str, str, str]] = set()
    triples_records: list[Triple] = []
    stats: dict[str, dict[str, int]] = {}

    for json_path in sorted(extracts_dir.glob("*.json")):
        doc_id = json_path.stem
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        ents_in: list[dict[str, object]] = data.get("entities", [])
        trips_in: list[dict[str, object]] = data.get("triples", [])

        kept_e = 0
        kept_t = 0
        rejected_e = 0
        rejected_t = 0

        for e in ents_in:
            name = str(e.get("name", "")).strip()
            type_id = str(e.get("type", "")).strip()
            if not name or not type_id:
                rejected_e += 1
                continue
            if not schema.is_valid_entity_type(type_id):
                rejected_e += 1
                continue
            aliases_raw = e.get("aliases", [])
            aliases: tuple[str, ...] = ()
            if isinstance(aliases_raw, list):
                aliases_strs: list[str] = []
                for a in aliases_raw:  # type: ignore[reportUnknownVariableType]
                    s = str(a).strip()  # type: ignore[reportUnknownArgumentType]
                    if s:
                        aliases_strs.append(s)
                aliases = tuple(aliases_strs)
            eid = _canonical_entity_id(name, type_id)
            existing = entities_by_id.get(eid)
            if existing is None:
                entities_by_id[eid] = Entity(
                    library_id=library_id,
                    entity_id=eid,
                    name=name,
                    aliases=aliases,
                    type=type_id,
                )
            else:
                merged = tuple(sorted(set(existing.aliases) | set(aliases)))
                entities_by_id[eid] = existing.model_copy(update={"aliases": merged})
            kept_e += 1

        for t in trips_in:
            head = str(t.get("head", "")).strip()
            tail = str(t.get("tail", "")).strip()
            relation = str(t.get("relation", "")).strip()
            head_type = str(t.get("head_type", "")).strip()
            tail_type = str(t.get("tail_type", "")).strip()
            if not all((head, tail, relation, head_type, tail_type)):
                rejected_t += 1
                continue
            try:
                schema.validate_triple(relation=relation, head_type=head_type, tail_type=tail_type)
            except SchemaValidationError:
                rejected_t += 1
                continue

            head_id = _canonical_entity_id(head, head_type)
            tail_id = _canonical_entity_id(tail, tail_type)

            evidence_raw = t.get("evidence_pages", [])
            evidence_pages: list[int] = []
            if isinstance(evidence_raw, list):
                for p in evidence_raw:  # type: ignore[reportUnknownVariableType]
                    if isinstance(p, int):
                        evidence_pages.append(p)
            evidence: tuple[str, ...] = tuple(f"{doc_id}::p{p}" for p in evidence_pages)
            if not evidence:
                evidence = (f"{doc_id}::p1",)

            confidence_raw = t.get("confidence", 0.85)
            confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.85
            confidence = max(0.0, min(1.0, confidence))

            key = (head_id, relation, tail_id)
            if key in triples_set:
                continue
            triples_set.add(key)

            triples_records.append(
                Triple(
                    library_id=library_id,
                    head=head_id,
                    relation=relation,
                    tail=tail_id,
                    evidence=evidence,
                    confidence=confidence,
                    source_model="claude-manual",
                )
            )
            kept_t += 1

        stats[doc_id] = {
            "entities_kept": kept_e,
            "entities_rejected": rejected_e,
            "triples_kept": kept_t,
            "triples_rejected": rejected_t,
        }

    return list(entities_by_id.values()), triples_records, stats


async def _ensure_entity_nodes_for_triples(
    entities: list[Entity],
    triples: list[Triple],
    library_id: str,
    schema: KGSchema,
) -> list[Entity]:
    """Ensure every triple endpoint has a corresponding Entity node.

    Some triples may reference entity_ids that no agent emitted as an
    explicit entity record (cross-paper references). Synthesize stub
    entities so the upsert succeeds.
    """
    by_id = {e.entity_id: e for e in entities}
    fallback_type = schema.entity_types[0].id if schema.entity_types else "Concept"

    needed: set[tuple[str, str]] = set()
    for t in triples:
        for endpoint in (t.head, t.tail):
            if endpoint in by_id:
                continue
            type_part = endpoint.split(":", 1)[0] if ":" in endpoint else fallback_type
            type_id = next(
                (et.id for et in schema.entity_types if et.id.lower() == type_part),
                fallback_type,
            )
            needed.add((endpoint, type_id))

    for endpoint, type_id in needed:
        name = endpoint.split(":", 1)[-1].replace("_", " ")
        by_id[endpoint] = Entity(
            library_id=library_id,
            entity_id=endpoint,
            name=name,
            type=type_id,
        )

    return list(by_id.values())


async def main_async(library_id: str) -> int:
    extracts_dir = Path("data/libraries") / library_id / "kg_extracts"
    if not extracts_dir.is_dir():
        console.print(f"[red]No KG extracts dir at {extracts_dir}[/red]")
        return 1

    schema = load_schema(library_id, Path("docs/ontology"))
    entities, triples, stats = _validate_and_collect(extracts_dir, library_id, schema)

    if not entities and not triples:
        console.print("[yellow]No valid entities or triples found in JSON files.[/yellow]")
        return 1

    container = build_container(library_id_for_schema=library_id)
    try:
        await container.graph_index.init_library(library_id)
        # Ensure stub entities exist for any cross-paper triple endpoints
        all_entities = await _ensure_entity_nodes_for_triples(entities, triples, library_id, schema)
        console.print(
            f"[cyan]Writing {len(all_entities)} entities + "
            f"{len(triples)} triples to Neo4j...[/cyan]"
        )
        await container.graph_index.upsert_entities(library_id, all_entities)
        await container.graph_index.upsert_triples(library_id, triples)
        kg_count = await container.graph_index.count_triples(library_id)
    finally:
        await container.aclose()

    table = Table(title=f"KG Load Summary — {library_id}")
    for col in ["doc_id", "entities ✓", "entities ✗", "triples ✓", "triples ✗"]:
        table.add_column(col)
    for doc_id, s in sorted(stats.items()):
        table.add_row(
            doc_id,
            str(s["entities_kept"]),
            str(s["entities_rejected"]),
            str(s["triples_kept"]),
            str(s["triples_rejected"]),
        )
    console.print(table)

    type_counts: dict[str, int] = defaultdict(int)
    for e in entities:
        type_counts[e.type] += 1
    rel_counts: dict[str, int] = defaultdict(int)
    for t in triples:
        rel_counts[t.relation] += 1

    console.print("\n[bold]Entity types:[/bold]")
    for t, n in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        console.print(f"  {t}: {n}")
    console.print("\n[bold]Relation types:[/bold]")
    for r, n in sorted(rel_counts.items(), key=lambda kv: -kv[1]):
        console.print(f"  {r}: {n}")

    console.print(
        f"\n[green]✓ Done.[/green] {len(entities)} unique entities, "
        f"{len(triples)} unique triples → Neo4j has {kg_count} triples total."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    args = parser.parse_args()
    return asyncio.run(main_async(args.library))


if __name__ == "__main__":
    raise SystemExit(main())
