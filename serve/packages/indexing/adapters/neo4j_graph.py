"""Neo4j-backed GraphIndex adapter.

Uses **label namespacing** for per-library isolation rather than the
composite-database feature (Community Edition limitation). Every node
is labeled `Lib_<library_id>` AND `<EntityType>`. Purging a library is
a single Cypher MATCH-DELETE on the lib label.

Why label namespacing over composite DB:
- Neo4j Community supports only one database
- Composite DB requires Enterprise license
- Label-based isolation is fast (indexed), cheap, and good enough for v1

Trade-off documented; revisit when scaling past ~1M nodes per library.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import LiteralString, cast

from neo4j import AsyncDriver, AsyncGraphDatabase

from packages.core.models import Entity, Triple
from packages.observability.instrumentation import instrumented
from packages.observability.metrics import RETRIEVAL_DURATION_SECONDS


def _cy(query: str) -> LiteralString:
    """Cast a runtime-built Cypher string to LiteralString.

    Neo4j's typed driver requires LiteralString to discourage SQL-injection-
    style attacks. Our Cypher is built from sanitized labels (only [a-zA-Z0-9_])
    plus parameterized values, so this cast is safe.
    """
    return cast(LiteralString, query)


@dataclass(frozen=True, slots=True)
class Neo4jGraphIndexConfig:
    """Neo4j connection settings."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "changeme"


def _lib_label(library_id: str) -> str:
    """Library-scope label. Sanitize to valid Cypher identifier."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", library_id)
    return f"Lib_{safe}"


def _entity_label(type_id: str) -> str:
    """Entity-type label. PascalCase, sanitized."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", type_id)
    return safe[:50] or "Entity"


class Neo4jGraphIndex:
    """GraphIndex adapter using Neo4j with label-namespace per-library isolation."""

    def __init__(self, config: Neo4jGraphIndexConfig) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password),
        )

    async def init_library(self, library_id: str) -> None:
        """Idempotent: create indexes on the library's namespace label."""
        label = _lib_label(library_id)
        async with self._driver.session() as session:
            await session.run(
                _cy(
                    f"CREATE INDEX entity_id_idx_{label} IF NOT EXISTS "
                    f"FOR (n:{label}) ON (n.entity_id)"
                )
            )

    async def purge_library(self, library_id: str) -> None:
        """Delete all nodes and relationships in the library namespace."""
        label = _lib_label(library_id)
        async with self._driver.session() as session:
            await session.run(_cy(f"MATCH (n:{label}) DETACH DELETE n"))
            with contextlib.suppress(Exception):
                await session.run(_cy(f"DROP INDEX entity_id_idx_{label} IF EXISTS"))

    @instrumented(
        op_name="neo4j.upsert_entities",
        component="neo4j",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "neo4j", "op": "upsert_entities"},
        label_from_arg={"library_id": "library_id"},
    )
    async def upsert_entities(self, library_id: str, entities: list[Entity]) -> None:
        if not entities:
            return
        lib_label = _lib_label(library_id)

        # Group by type so we can apply the right per-type label
        by_type: dict[str, list[Entity]] = {}
        for e in entities:
            by_type.setdefault(_entity_label(e.type), []).append(e)

        async with self._driver.session() as session:
            for type_label, group in by_type.items():
                payload = [
                    {
                        "entity_id": e.entity_id,
                        "name": e.name,
                        "aliases": list(e.aliases),
                        "type": e.type,
                        "description": e.description or "",
                    }
                    for e in group
                ]
                cypher = (
                    f"UNWIND $rows AS row "
                    f"MERGE (n:{lib_label}:{type_label} {{entity_id: row.entity_id}}) "
                    f"SET n.name = row.name, "
                    f"    n.aliases = row.aliases, "
                    f"    n.type = row.type, "
                    f"    n.description = row.description, "
                    f"    n.library_id = $library_id"
                )
                await session.run(_cy(cypher), rows=payload, library_id=library_id)

    @instrumented(
        op_name="neo4j.upsert_triples",
        component="neo4j",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "neo4j", "op": "upsert_triples"},
        label_from_arg={"library_id": "library_id"},
    )
    async def upsert_triples(self, library_id: str, triples: list[Triple]) -> None:
        if not triples:
            return
        lib_label = _lib_label(library_id)

        # Group by relation so we can use a typed RELATIONSHIP per Cypher call
        by_rel: dict[str, list[Triple]] = {}
        for t in triples:
            by_rel.setdefault(_entity_label(t.relation), []).append(t)

        async with self._driver.session() as session:
            for rel_type, group in by_rel.items():
                payload = [
                    {
                        "head": t.head,
                        "tail": t.tail,
                        "evidence": list(t.evidence),
                        "confidence": t.confidence,
                        "source_model": t.source_model,
                    }
                    for t in group
                ]
                cypher = (
                    f"UNWIND $rows AS row "
                    f"MATCH (h:{lib_label} {{entity_id: row.head}}) "
                    f"MATCH (t:{lib_label} {{entity_id: row.tail}}) "
                    f"MERGE (h)-[r:{rel_type}]->(t) "
                    f"SET r.evidence = row.evidence, "
                    f"    r.confidence = row.confidence, "
                    f"    r.source_model = row.source_model, "
                    f"    r.library_id = $library_id"
                )
                await session.run(_cy(cypher), rows=payload, library_id=library_id)

    @instrumented(
        op_name="neo4j.get_neighbors",
        component="neo4j",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "neo4j", "op": "get_neighbors"},
        label_from_arg={"library_id": "library_id"},
    )
    async def get_neighbors(
        self,
        library_id: str,
        entity_id: str,
        depth: int = 1,
    ) -> list[Triple]:
        """Return triples within `depth` hops of the given entity."""
        lib_label = _lib_label(library_id)
        depth = max(1, min(depth, 3))

        cypher = (
            f"MATCH (root:{lib_label} {{entity_id: $entity_id}}) "
            f"MATCH path = (root)-[*1..{depth}]-(neighbor:{lib_label}) "
            f"WITH relationships(path) AS rels "
            f"UNWIND rels AS r "
            f"WITH DISTINCT r "
            f"MATCH (h)-[r]->(t) "
            f"RETURN h.entity_id AS head, type(r) AS relation, t.entity_id AS tail, "
            f"       r.evidence AS evidence, r.confidence AS confidence, "
            f"       r.source_model AS source_model"
        )

        triples: list[Triple] = []
        async with self._driver.session() as session:
            result = await session.run(_cy(cypher), entity_id=entity_id)
            async for record in result:
                evidence_field: object = record["evidence"]
                evidence_list: list[str] = []
                if isinstance(evidence_field, list):
                    for e in evidence_field:  # type: ignore[reportUnknownVariableType]
                        evidence_list.append(str(e))  # type: ignore[reportUnknownArgumentType]
                evidence_tuple = tuple(evidence_list)
                if not evidence_tuple:
                    # Triples without evidence violate provenance rule; skip
                    continue
                try:
                    triples.append(
                        Triple(
                            library_id=library_id,
                            head=str(record["head"]),
                            relation=str(record["relation"]),
                            tail=str(record["tail"]),
                            evidence=evidence_tuple,
                            confidence=float(record["confidence"] or 0.0),
                            source_model=str(record["source_model"] or ""),
                        )
                    )
                except (ValueError, TypeError):
                    continue
        return triples

    async def count_triples(self, library_id: str) -> int:
        """Diagnostic: count triples in the library."""
        lib_label = _lib_label(library_id)
        cypher = f"MATCH (:{lib_label})-[r]->(:{lib_label}) RETURN count(r) AS cnt"
        async with self._driver.session() as session:
            result = await session.run(_cy(cypher))
            record = await result.single()
            return int(record["cnt"]) if record else 0

    @instrumented(
        op_name="neo4j.list_all_triples",
        component="neo4j",
        histogram=RETRIEVAL_DURATION_SECONDS,
        histogram_labels={"component": "neo4j", "op": "list_all_triples"},
        label_from_arg={"library_id": "library_id"},
    )
    async def list_all_triples(self, library_id: str) -> list[Triple]:
        """Return every triple in the library namespace.

        Used by community detection / global search rebuild jobs.
        For very large KGs (10M+ triples) consider streaming or seeded
        traversal instead.
        """
        lib_label = _lib_label(library_id)
        cypher = (
            f"MATCH (h:{lib_label})-[r]->(t:{lib_label}) "
            f"RETURN h.entity_id AS head, type(r) AS relation, t.entity_id AS tail, "
            f"       coalesce(r.evidence, []) AS evidence, "
            f"       coalesce(r.confidence, 0.0) AS confidence, "
            f"       coalesce(r.source_model, '') AS source_model"
        )

        triples: list[Triple] = []
        async with self._driver.session() as session:
            result = await session.run(_cy(cypher))
            async for record in result:
                evidence_field: object = record["evidence"]
                evidence_list: list[str] = []
                if isinstance(evidence_field, list):
                    for e in evidence_field:  # type: ignore[reportUnknownVariableType]
                        evidence_list.append(str(e))  # type: ignore[reportUnknownArgumentType]
                evidence_tuple = tuple(evidence_list) or ("auto",)
                try:
                    triples.append(
                        Triple(
                            library_id=library_id,
                            head=str(record["head"]),
                            relation=str(record["relation"]),
                            tail=str(record["tail"]),
                            evidence=evidence_tuple,
                            confidence=float(record["confidence"] or 0.0),
                            source_model=str(record["source_model"] or ""),
                        )
                    )
                except (ValueError, TypeError):
                    continue
        return triples

    async def list_entities(self, library_id: str) -> list[Entity]:
        """Return every entity in the library namespace."""
        lib_label = _lib_label(library_id)
        cypher = (
            f"MATCH (n:{lib_label}) "
            f"RETURN coalesce(n.entity_id, '') AS entity_id, "
            f"       coalesce(n.name, n.entity_id, '') AS name, "
            f"       coalesce(n.aliases, []) AS aliases, "
            f"       coalesce(n.type, 'Entity') AS type, "
            f"       coalesce(n.description, '') AS description"
        )

        entities: list[Entity] = []
        async with self._driver.session() as session:
            result = await session.run(_cy(cypher))
            async for record in result:
                entity_id = str(record["entity_id"])
                name = str(record["name"])
                if not entity_id or not name:
                    continue
                aliases_field: object = record["aliases"]
                aliases: list[str] = []
                if isinstance(aliases_field, list):
                    for item in cast("list[object]", aliases_field):
                        aliases.append(str(item))
                description = str(record["description"] or "")
                try:
                    entities.append(
                        Entity(
                            library_id=library_id,
                            entity_id=entity_id,
                            name=name,
                            aliases=tuple(aliases),
                            type=str(record["type"] or "Entity"),
                            description=description or None,
                        )
                    )
                except (ValueError, TypeError):
                    continue
        return entities

    async def close(self) -> None:
        await self._driver.close()
