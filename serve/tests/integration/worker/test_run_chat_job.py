"""Integration test for the durable frontend chat worker job."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apps.worker.jobs import run_chat
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import SqliteMemoryStore
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.core.models import Chunk
from packages.orchestration.protocols import AnsweredQuery, Citation, TokenUsage
from packages.orchestration.queue import TaskEventType
from packages.retrieval.protocols import RetrievedEvidence


class _FakeQATask:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def answer_in_conversation(
        self,
        *,
        library_id: str,
        conversation: Any,
        question: str,
        context_service: ContextService,
        rewriter: Any,
        compactor: Any,
        memory: Any,
        composer: Any,
        settings_snapshot: Any,
        library_card: str = "",
        budget: Any = None,
    ) -> AnsweredQuery:
        _ = rewriter, compactor, memory, composer, settings_snapshot, library_card, budget
        self.calls.append(
            {
                "library_id": library_id,
                "conversation_id": conversation.conversation_id,
                "question": question,
            }
        )
        await context_service.append_user_turn(conversation=conversation, content=question)
        citations = (
            Citation(
                chunk_id="chunk-1",
                doc_id="2210.03629",
                page=2,
                snippet="Graph retrieval grounds synthesis.",
            ),
        )
        await context_service.append_assistant_turn(
            conversation=conversation,
            content="GraphRAG combines graph retrieval with grounded synthesis.",
            citations=citations,
            model="fake-chat",
            input_tokens=12,
            output_tokens=8,
        )
        retrieved = (
            RetrievedEvidence(
                chunk=Chunk(
                    library_id=library_id,
                    chunk_id="chunk-1",
                    doc_id="2210.03629",
                    text="Graph retrieval grounds synthesis.",
                    page=2,
                ),
                score=0.941,
                source="vector",
            ),
        )
        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer="GraphRAG combines graph retrieval with grounded synthesis.",
            citations=citations,
            retrieved=retrieved,
            model="fake-chat",
            tokens=TokenUsage(input_tokens=12, output_tokens=8),
            duration_ms=42,
        )


@pytest.mark.asyncio
async def test_run_chat_emits_answer_events_and_persists_turns(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run_chat, "_TOKEN_DELAY_S", 0)
    db_path = tmp_path / "context.sqlite"
    context_service = ContextService(
        store=SqliteConversationRepo(db_path),
        memory_store=SqliteMemoryStore(db_path),
    )
    conversation = await context_service.open(
        library_id="test-lib",
        autocreate_title="GraphRAG",
    )
    qa_task = _FakeQATask()
    ctx = {
        **base_ctx,
        "settings": Settings(data_dir=str(tmp_path / "data")),
        "qa_task": qa_task,
        "context_service": context_service,
    }

    result = await run_chat.run(
        ctx,
        library_id="test-lib",
        task_id="chat-task-1",
        input_payload={
            "conversation_id": conversation.conversation_id,
            "question": "How does GraphRAG answer?",
        },
    )

    assert result == {
        "conversation_id": conversation.conversation_id,
        "citation_count": 1,
        "evidence_count": 1,
    }
    assert qa_task.calls == [
        {
            "library_id": "test-lib",
            "conversation_id": conversation.conversation_id,
            "question": "How does GraphRAG answer?",
        }
    ]
    event_types = [event.type for event in fake_event_bus.events]
    assert TaskEventType.TASK_STARTED in event_types
    assert TaskEventType.TOKEN in event_types
    assert TaskEventType.STAGE_COMPLETED in event_types
    assert TaskEventType.CITATION_ADDED in event_types
    assert TaskEventType.TASK_COMPLETED in event_types
    assert any(event.payload.get("token") for event in fake_event_bus.events)
    assert any(event.payload.get("evidence") for event in fake_event_bus.events)
    assert any(event.payload.get("citation_ids") == ["chunk-1"] for event in fake_event_bus.events)

    turns = await context_service.history(conversation.conversation_id)
    assert [turn.role for turn in turns] == ["user", "assistant"]
