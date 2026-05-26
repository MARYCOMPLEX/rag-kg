"""Tests for the `ContextService` facade.

These exercise the facade against the real `SqliteConversationRepo` because
both are owned by M8.A5 and the test pair is small enough that an in-memory
db file (under tmp_path) is the most honest substitute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.service import ContextService
from packages.orchestration.protocols import Citation


@pytest.fixture
def service(tmp_path: Path) -> ContextService:
    """A `ContextService` over a temp-file sqlite repo."""
    repo = SqliteConversationRepo(tmp_path / "context.sqlite")
    return ContextService(store=repo)


async def test_open_without_id_creates_fresh_conversation(
    service: ContextService,
) -> None:
    # Act
    conv = await service.open(library_id="lib-a", autocreate_title="Untitled chat")

    # Assert — a fresh conversation has a generated id and the requested title
    assert conv.library_id == "lib-a"
    assert conv.title == "Untitled chat"
    assert conv.summary == ""
    assert conv.conversation_id  # non-empty
    assert len(conv.conversation_id) == 16
    await service.aclose()


async def test_open_with_valid_id_returns_existing(
    service: ContextService,
) -> None:
    # Arrange
    created = await service.open(library_id="lib-a", autocreate_title="t")

    # Act
    fetched = await service.open(library_id="lib-a", conversation_id=created.conversation_id)

    # Assert
    assert fetched.conversation_id == created.conversation_id
    assert fetched.title == "t"
    await service.aclose()


async def test_open_with_missing_id_raises(service: ContextService) -> None:
    with pytest.raises(ValueError, match="not found in lib-a"):
        await service.open(library_id="lib-a", conversation_id="ghost-id")
    await service.aclose()


async def test_append_user_and_assistant_turn_persist_correctly(
    service: ContextService,
) -> None:
    # Arrange
    conv = await service.open(library_id="lib-a")
    citations = (Citation(chunk_id="ch-1", doc_id="doc-1", page=2, snippet="evidence"),)

    # Act
    user_turn = await service.append_user_turn(
        conversation=conv,
        content="What is RAG?",
        rewritten_query=None,
    )
    assistant_turn = await service.append_assistant_turn(
        conversation=conv,
        content="Retrieval-Augmented Generation.",
        citations=citations,
        model="deepseek-v4-flash",
        input_tokens=120,
        output_tokens=18,
    )

    # Assert
    assert user_turn.role == "user"
    assert user_turn.content == "What is RAG?"
    assert user_turn.input_tokens == 0
    assert user_turn.output_tokens == 0
    assert user_turn.citations == ()

    assert assistant_turn.role == "assistant"
    assert assistant_turn.content == "Retrieval-Augmented Generation."
    assert assistant_turn.input_tokens == 120
    assert assistant_turn.output_tokens == 18
    assert assistant_turn.model == "deepseek-v4-flash"
    assert assistant_turn.citations == citations
    await service.aclose()


async def test_update_summary_returns_new_conversation_with_bumped_updated_at(
    service: ContextService,
) -> None:
    # Arrange
    conv = await service.open(library_id="lib-a", autocreate_title="t")
    original_updated_at = conv.updated_at

    # Act
    bumped = await service.update_summary(conversation=conv, summary="A short summary.")

    # Assert — return value is a NEW Conversation with updated fields
    assert bumped is not conv
    assert bumped.summary == "A short summary."
    assert bumped.updated_at >= original_updated_at
    # The original frozen instance is unchanged
    assert conv.summary == ""

    # And the persisted row reflects the new summary
    persisted = await service.open(library_id="lib-a", conversation_id=conv.conversation_id)
    assert persisted.summary == "A short summary."
    await service.aclose()


async def test_update_title_persists_and_returns_new_conversation(
    service: ContextService,
) -> None:
    # Arrange
    conv = await service.open(library_id="lib-a", autocreate_title="placeholder")

    # Act
    titled = await service.update_title(conversation=conv, title="Cats and physics")

    # Assert
    assert titled.title == "Cats and physics"
    assert conv.title == "placeholder"  # frozen original untouched

    persisted = await service.open(library_id="lib-a", conversation_id=conv.conversation_id)
    assert persisted.title == "Cats and physics"
    await service.aclose()


async def test_history_returns_turns_in_insertion_order(
    service: ContextService,
) -> None:
    # Arrange
    conv = await service.open(library_id="lib-a")
    await service.append_user_turn(conversation=conv, content="Q1")
    await service.append_assistant_turn(
        conversation=conv,
        content="A1",
        citations=(),
        model="m",
        input_tokens=1,
        output_tokens=1,
    )
    await service.append_user_turn(conversation=conv, content="Q2")

    # Act
    turns = await service.history(conv.conversation_id)

    # Assert
    assert tuple(t.content for t in turns) == ("Q1", "A1", "Q2")
    assert tuple(t.role for t in turns) == ("user", "assistant", "user")
    await service.aclose()


async def test_list_returns_only_target_library(service: ContextService) -> None:
    # Arrange
    a1 = await service.open(library_id="lib-a", autocreate_title="A1")
    a2 = await service.open(library_id="lib-a", autocreate_title="A2")
    b1 = await service.open(library_id="lib-b", autocreate_title="B1")

    # Act
    lib_a = await service.list("lib-a")
    lib_b = await service.list("lib-b")

    # Assert
    a_ids = {c.conversation_id for c in lib_a}
    b_ids = {c.conversation_id for c in lib_b}
    assert a_ids == {a1.conversation_id, a2.conversation_id}
    assert b_ids == {b1.conversation_id}
    await service.aclose()


async def test_delete_removes_conversation_and_subsequent_open_raises(
    service: ContextService,
) -> None:
    # Arrange
    conv = await service.open(library_id="lib-a", autocreate_title="doomed")
    await service.append_user_turn(conversation=conv, content="hi")

    # Act
    await service.delete(library_id="lib-a", conversation_id=conv.conversation_id)

    # Assert
    with pytest.raises(ValueError, match="not found"):
        await service.open(library_id="lib-a", conversation_id=conv.conversation_id)
    # And history is empty (cascade)
    assert await service.history(conv.conversation_id) == ()
    await service.aclose()
