"""String-based entity linker.

Canonicalizes entities by deduplicating on entity_id (already a
type:slug(name) construction in the extractor) and merging aliases.

For M2 baseline this is sufficient — the LLM extractor produces
deterministic IDs from name+type. M3+ may upgrade to embedding-based
linking for cross-spelling-variant handling.
"""

from __future__ import annotations

from packages.core.models import Entity


class StringEntityLinker:
    """Merge entities sharing the same canonical entity_id."""

    async def link(self, library_id: str, entities: list[Entity]) -> list[Entity]:
        if not entities:
            return []

        merged: dict[str, Entity] = {}
        for e in entities:
            if e.library_id != library_id:
                continue
            existing = merged.get(e.entity_id)
            if existing is None:
                merged[e.entity_id] = e
                continue
            aliases = tuple(sorted(set(existing.aliases) | set(e.aliases) | {e.name}))
            if existing.name in aliases:
                aliases = tuple(a for a in aliases if a != existing.name)
            merged[e.entity_id] = existing.model_copy(update={"aliases": aliases})

        return sorted(merged.values(), key=lambda e: e.entity_id)
