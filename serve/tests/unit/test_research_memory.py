"""Unit tests for `SqliteMemoryStore` and `ResearchMemory` (M8.A4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.protocols import MemoryEntry


def _make_entry(
    *,
    library_id: str = "lib-a",
    entry_id: str = "e1",
    kind: str = "user",
    title: str = "Title",
    content: str = "Body",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MemoryEntry:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MemoryEntry(
        library_id=library_id,
        entry_id=entry_id,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        content=content,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


@pytest.fixture
def store(tmp_path: Path) -> SqliteMemoryStore:
    return SqliteMemoryStore(tmp_path / "memory.sqlite")


@pytest.fixture
def memory(store: SqliteMemoryStore) -> ResearchMemory:
    return ResearchMemory(store=store, max_entries_in_prompt=5)


class TestSqliteMemoryStore:
    async def test_create_and_get_round_trip(self, store: SqliteMemoryStore) -> None:
        # Arrange
        entry = _make_entry(entry_id="abc", title="Pref", content="Like surveys")

        # Act
        await store.upsert_entry(entry)
        got = await store.get_entry("lib-a", "abc")

        # Assert
        assert got is not None
        assert got.entry_id == "abc"
        assert got.title == "Pref"
        assert got.content == "Like surveys"
        assert got.kind == "user"

    async def test_list_entries_orders_by_updated_at_desc(self, store: SqliteMemoryStore) -> None:
        # Arrange
        base = datetime(2026, 1, 1, tzinfo=UTC)
        older = _make_entry(entry_id="old", updated_at=base)
        newer = _make_entry(entry_id="new", updated_at=base + timedelta(hours=1))
        newest = _make_entry(entry_id="newest", updated_at=base + timedelta(hours=2))
        await store.upsert_entry(older)
        await store.upsert_entry(newer)
        await store.upsert_entry(newest)

        # Act
        entries = await store.list_entries("lib-a")

        # Assert
        assert tuple(e.entry_id for e in entries) == ("newest", "new", "old")

    async def test_upsert_preserves_created_at_and_bumps_updated_at(
        self, store: SqliteMemoryStore
    ) -> None:
        # Arrange
        created = datetime(2026, 1, 1, tzinfo=UTC)
        original = _make_entry(entry_id="x", title="v1", created_at=created, updated_at=created)
        await store.upsert_entry(original)

        later = created + timedelta(days=1)
        bumped = original.model_copy(update={"title": "v2", "updated_at": later})

        # Act
        await store.upsert_entry(bumped)
        got = await store.get_entry("lib-a", "x")

        # Assert
        assert got is not None
        assert got.title == "v2"
        assert got.created_at == created
        assert got.updated_at == later

    async def test_delete_is_idempotent(self, store: SqliteMemoryStore) -> None:
        # Act + Assert: deleting absent entry must not raise.
        await store.delete_entry("lib-a", "missing")

        # Arrange + Act: delete-after-create removes the row, second delete is a no-op.
        await store.upsert_entry(_make_entry(entry_id="d1"))
        await store.delete_entry("lib-a", "d1")
        await store.delete_entry("lib-a", "d1")

        # Assert
        assert await store.get_entry("lib-a", "d1") is None

    async def test_cross_library_isolation(self, store: SqliteMemoryStore) -> None:
        # Arrange
        await store.upsert_entry(_make_entry(library_id="lib-a", entry_id="a1"))
        await store.upsert_entry(_make_entry(library_id="lib-a", entry_id="a2"))
        await store.upsert_entry(_make_entry(library_id="lib-b", entry_id="b1"))

        # Act
        a_entries = await store.list_entries("lib-a")
        b_entries = await store.list_entries("lib-b")

        # Assert
        assert {e.entry_id for e in a_entries} == {"a1", "a2"}
        assert {e.entry_id for e in b_entries} == {"b1"}
        assert await store.get_entry("lib-b", "a1") is None


class TestResearchMemoryFacade:
    async def test_create_persists_with_generated_id(
        self, memory: ResearchMemory, store: SqliteMemoryStore
    ) -> None:
        # Act
        entry = await memory.create("lib-a", "user", "Tone", "Explain like a CS PhD")

        # Assert
        assert len(entry.entry_id) == 16
        round_tripped = await store.get_entry("lib-a", entry.entry_id)
        assert round_tripped is not None
        assert round_tripped.title == "Tone"

    async def test_update_patches_only_provided_fields(self, memory: ResearchMemory) -> None:
        # Arrange
        entry = await memory.create("lib-a", "user", "Old", "Old body")

        # Act
        updated = await memory.update("lib-a", entry.entry_id, content="New body")

        # Assert
        assert updated is not None
        assert updated.title == "Old"  # unchanged
        assert updated.content == "New body"
        assert updated.created_at == entry.created_at
        assert updated.updated_at >= entry.updated_at

    async def test_update_returns_none_for_missing_entry(self, memory: ResearchMemory) -> None:
        # Act
        result = await memory.update("lib-a", "no-such-id", title="x")

        # Assert
        assert result is None

    async def test_delete_idempotent_via_facade(self, memory: ResearchMemory) -> None:
        # Arrange
        entry = await memory.create("lib-a", "user", "T", "C")

        # Act
        await memory.delete("lib-a", entry.entry_id)
        await memory.delete("lib-a", entry.entry_id)
        after = await memory.list("lib-a")

        # Assert
        assert after == ()

    async def test_select_relevant_returns_empty_when_memory_empty(
        self, memory: ResearchMemory
    ) -> None:
        # Act
        picked = await memory.select_relevant("lib-a", "anything")

        # Assert
        assert picked == ()

    async def test_select_relevant_prefers_user_feedback_then_overlap(
        self, store: SqliteMemoryStore
    ) -> None:
        # Arrange — three entries: one project (no priority), one feedback (priority,
        # high overlap), one user (priority, low overlap). The ranking should be:
        # feedback > user > project.
        base = datetime(2026, 1, 1, tzinfo=UTC)
        project_entry = _make_entry(
            entry_id="p1",
            kind="project",
            title="NeurIPS retrieval submission",
            content="retrieval retrieval retrieval",
            updated_at=base + timedelta(hours=3),
        )
        feedback_entry = _make_entry(
            entry_id="f1",
            kind="feedback",
            title="Citation style",
            content="always cite the original retrieval paper",
            updated_at=base + timedelta(hours=1),
        )
        user_entry = _make_entry(
            entry_id="u1",
            kind="user",
            title="Audience",
            content="explain like a phd",
            updated_at=base + timedelta(hours=2),
        )
        await store.upsert_entry(project_entry)
        await store.upsert_entry(feedback_entry)
        await store.upsert_entry(user_entry)
        memory = ResearchMemory(store=store, max_entries_in_prompt=2)

        # Act
        picked = await memory.select_relevant("lib-a", "retrieval citation")

        # Assert — only priority kinds in top-2; feedback wins on overlap.
        assert tuple(e.entry_id for e in picked) == ("f1", "u1")

    async def test_render_block_empty_returns_empty_string(self, memory: ResearchMemory) -> None:
        # Act
        rendered = await memory.render_block(())

        # Assert
        assert rendered == ""

    async def test_render_block_populated_has_no_stray_whitespace(
        self, memory: ResearchMemory
    ) -> None:
        # Arrange
        entries = (
            _make_entry(entry_id="r1", kind="user", title="Tone", content="Explain like a PhD"),
            _make_entry(
                entry_id="r2",
                kind="feedback",
                title="Cite",
                content="Always cite originals",
            ),
        )

        # Act
        rendered = await memory.render_block(entries)

        # Assert
        assert rendered == (
            "- [user] Tone: Explain like a PhD\n- [feedback] Cite: Always cite originals"
        )
        assert not rendered.startswith(("\n", " "))
        assert not rendered.endswith(("\n", " "))

    async def test_render_block_truncates_long_content(self, memory: ResearchMemory) -> None:
        # Arrange — content > 240 chars must be truncated with an ellipsis.
        long_content = "x" * 500
        entry = _make_entry(entry_id="long", content=long_content)

        # Act
        rendered = await memory.render_block((entry,))

        # Assert
        assert rendered.endswith("...")
        # Original 500 char content is gone; only the head + ellipsis remains.
        assert rendered.count("x") <= 240
