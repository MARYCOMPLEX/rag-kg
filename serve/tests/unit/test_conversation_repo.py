"""Tests for the sqlite-backed `SqliteConversationRepo`."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.protocols import Conversation, Turn
from packages.orchestration.protocols import Citation


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_conversation(
    *,
    library_id: str = "lib-a",
    conversation_id: str = "conv-1",
    title: str = "First conversation",
    summary: str = "",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Conversation:
    base = created_at or _now()
    return Conversation(
        library_id=library_id,
        conversation_id=conversation_id,
        title=title,
        summary=summary,
        created_at=base,
        updated_at=updated_at or base,
    )


def _make_turn(
    *,
    conversation_id: str = "conv-1",
    turn_id: str = "t-1",
    role: str = "user",
    content: str = "Hello?",
    citations: tuple[Citation, ...] = (),
    created_at: datetime | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str | None = None,
    rewritten_query: str | None = None,
) -> Turn:
    return Turn(
        conversation_id=conversation_id,
        turn_id=turn_id,
        role=role,  # type: ignore[arg-type]
        content=content,
        citations=citations,
        rewritten_query=rewritten_query,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        created_at=created_at or _now(),
    )


@pytest.fixture
def repo(tmp_path: Path) -> SqliteConversationRepo:
    """A fresh sqlite repo backed by a per-test temp file."""
    return SqliteConversationRepo(tmp_path / "context.sqlite")


async def test_create_and_get_round_trip(repo: SqliteConversationRepo) -> None:
    # Arrange
    conv = _make_conversation(title="Inbox zero")

    # Act
    await repo.create_conversation(conv)
    fetched = await repo.get_conversation(conv.library_id, conv.conversation_id)

    # Assert
    assert fetched is not None
    assert fetched.conversation_id == conv.conversation_id
    assert fetched.title == "Inbox zero"
    assert fetched.summary == ""
    await repo.close()


async def test_get_missing_returns_none(repo: SqliteConversationRepo) -> None:
    assert await repo.get_conversation("lib-a", "missing") is None
    await repo.close()


async def test_list_conversations_orders_by_updated_at_desc(
    repo: SqliteConversationRepo,
) -> None:
    # Arrange — three conversations with explicit, well-separated timestamps
    base = _now()
    older = _make_conversation(
        conversation_id="c-old",
        title="oldest",
        created_at=base - timedelta(hours=2),
        updated_at=base - timedelta(hours=2),
    )
    middle = _make_conversation(
        conversation_id="c-mid",
        title="middle",
        created_at=base - timedelta(hours=1),
        updated_at=base - timedelta(hours=1),
    )
    newest = _make_conversation(
        conversation_id="c-new",
        title="newest",
        created_at=base,
        updated_at=base,
    )
    for c in (older, middle, newest):
        await repo.create_conversation(c)

    # Act
    listed = await repo.list_conversations("lib-a")

    # Assert
    assert tuple(c.conversation_id for c in listed) == ("c-new", "c-mid", "c-old")
    await repo.close()


async def test_update_conversation_persists_summary_and_bumps_updated_at(
    repo: SqliteConversationRepo,
) -> None:
    # Arrange
    base = _now()
    conv = _make_conversation(created_at=base, updated_at=base)
    await repo.create_conversation(conv)

    # Act
    bumped = conv.model_copy(
        update={
            "summary": "User asked about cats. Assistant explained whiskers.",
            "updated_at": base + timedelta(minutes=5),
        }
    )
    await repo.update_conversation(bumped)

    # Assert
    fetched = await repo.get_conversation(conv.library_id, conv.conversation_id)
    assert fetched is not None
    assert fetched.summary.startswith("User asked about cats")
    assert fetched.updated_at > conv.updated_at
    await repo.close()


async def test_append_turn_and_list_turns_in_chronological_order(
    repo: SqliteConversationRepo,
) -> None:
    # Arrange
    base = _now()
    conv = _make_conversation()
    await repo.create_conversation(conv)
    t1 = _make_turn(turn_id="t-1", role="user", content="Q1?", created_at=base)
    t2 = _make_turn(
        turn_id="t-2",
        role="assistant",
        content="A1.",
        created_at=base + timedelta(seconds=1),
    )
    t3 = _make_turn(
        turn_id="t-3",
        role="user",
        content="Q2?",
        created_at=base + timedelta(seconds=2),
    )

    # Act — append out of chronological order on purpose
    await repo.append_turn(t2)
    await repo.append_turn(t1)
    await repo.append_turn(t3)
    listed = await repo.list_turns(conv.conversation_id)

    # Assert — list_turns must order by created_at ASC regardless of insert order
    assert tuple(t.turn_id for t in listed) == ("t-1", "t-2", "t-3")
    assert listed[0].role == "user"
    assert listed[1].role == "assistant"
    await repo.close()


async def test_delete_conversation_cascades_to_turns(
    repo: SqliteConversationRepo,
) -> None:
    # Arrange
    conv = _make_conversation()
    await repo.create_conversation(conv)
    await repo.append_turn(_make_turn(turn_id="t-1"))
    await repo.append_turn(_make_turn(turn_id="t-2", role="assistant", content="ok"))
    assert len(await repo.list_turns(conv.conversation_id)) == 2

    # Act
    await repo.delete_conversation(conv.library_id, conv.conversation_id)

    # Assert — both the conversation and its turns are gone
    assert await repo.get_conversation(conv.library_id, conv.conversation_id) is None
    assert await repo.list_turns(conv.conversation_id) == ()
    await repo.close()


async def test_cross_library_isolation(repo: SqliteConversationRepo) -> None:
    # Arrange — distinct conversations in two libraries; conversation_id is
    # globally unique (so the turns FK can reference it), so we use distinct ids.
    a = _make_conversation(library_id="lib-a", conversation_id="conv-a-1", title="A")
    b = _make_conversation(library_id="lib-b", conversation_id="conv-b-1", title="B")
    await repo.create_conversation(a)
    await repo.create_conversation(b)

    # Act
    list_a = await repo.list_conversations("lib-a")
    list_b = await repo.list_conversations("lib-b")
    fetched_b_in_a = await repo.get_conversation("lib-a", "conv-b-1")
    fetched_a = await repo.get_conversation("lib-a", "conv-a-1")

    # Assert — each library sees only its own row
    assert len(list_a) == 1
    assert list_a[0].title == "A"
    assert len(list_b) == 1
    assert list_b[0].title == "B"

    # Cross-library lookup of a conversation that exists in another library
    # must return None — the (library_id, conversation_id) tuple is the key.
    assert fetched_b_in_a is None
    assert fetched_a is not None
    assert fetched_a.title == "A"

    # And listing a missing library yields empty
    assert await repo.list_conversations("lib-missing") == ()
    await repo.close()


async def test_citations_round_trip(repo: SqliteConversationRepo) -> None:
    # Arrange
    conv = _make_conversation()
    await repo.create_conversation(conv)
    citations = (
        Citation(chunk_id="ch-1", doc_id="doc-a", page=3, snippet="cats purr"),
        Citation(chunk_id="ch-2", doc_id="doc-b", page=None, snippet=""),
    )
    turn = _make_turn(
        turn_id="t-cite",
        role="assistant",
        content="Cats purr at 25 Hz.",
        citations=citations,
        model="fake-model",
        input_tokens=120,
        output_tokens=42,
        rewritten_query="why do cats purr",
    )

    # Act
    await repo.append_turn(turn)
    listed = await repo.list_turns(conv.conversation_id)

    # Assert — citations + scalar fields all preserved
    assert len(listed) == 1
    got = listed[0]
    assert got.citations == citations
    assert got.model == "fake-model"
    assert got.input_tokens == 120
    assert got.output_tokens == 42
    assert got.rewritten_query == "why do cats purr"
    await repo.close()


async def test_close_is_safe_to_call(repo: SqliteConversationRepo) -> None:
    # Arrange / Act — close should not raise
    await repo.close()
    # Assert — sentinel: a follow-up ops on a closed conn would raise; we
    # just verify close itself completes cleanly
    await asyncio.sleep(0)
