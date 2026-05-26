"""Sentence-based chunker with character-window sliding and overlap.

Stays simple — no model dependency. Produces ~512–1024 char chunks with
~100 char overlap. Good enough for embedding most retrievers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.core.models import Chunk
from packages.ingestion.protocols import ParsedDocument, ParsedSection

# Match sentence terminators in English and CJK
_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


@dataclass(frozen=True, slots=True)
class SentenceChunkerConfig:
    """Tunables for the sentence chunker."""

    target_chars: int = 800
    overlap_chars: int = 100
    min_chars: int = 100
    max_chars: int = 1500


class SentenceChunker:
    """Split parsed sections into chunks with sentence-aware overlap."""

    def __init__(self, config: SentenceChunkerConfig | None = None) -> None:
        self._config = config or SentenceChunkerConfig()

    def chunk(self, library_id: str, parsed: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        global_idx = 0
        for section in parsed.sections:
            for chunk_text, char_start, char_end in self._split_section(section):
                if len(chunk_text) < self._config.min_chars:
                    continue
                chunks.append(
                    Chunk(
                        library_id=library_id,
                        chunk_id=f"{parsed.document.doc_id}::p{section.page or 0}::{global_idx}",
                        doc_id=parsed.document.doc_id,
                        text=chunk_text,
                        page=section.page,
                        section=section.title,
                        kind="text",
                        offset=(char_start, char_end),
                    )
                )
                global_idx += 1
        return chunks

    def _split_section(self, section: ParsedSection) -> list[tuple[str, int, int]]:
        text = section.text.strip()
        if not text:
            return []

        sentences = _split_into_sentences(text)
        if not sentences:
            return []

        results: list[tuple[str, int, int]] = []
        buf: list[str] = []
        buf_len = 0
        char_cursor = 0
        chunk_start = 0

        for sent in sentences:
            sent_len = len(sent)
            if buf_len + sent_len + 1 > self._config.target_chars and buf:
                joined = " ".join(buf).strip()
                if joined:
                    results.append((joined, chunk_start, chunk_start + len(joined)))
                buf, buf_len, chunk_start = self._roll_overlap(buf, char_cursor)
            buf.append(sent)
            buf_len += sent_len + 1
            char_cursor += sent_len + 1

        if buf:
            joined = " ".join(buf).strip()
            if joined:
                results.append((joined, chunk_start, chunk_start + len(joined)))

        return [self._truncate(c) for c in results if c[0]]

    def _roll_overlap(self, prev_buf: list[str], cursor: int) -> tuple[list[str], int, int]:
        """Carry the tail of prev_buf as overlap context for next chunk."""
        overlap_target = self._config.overlap_chars
        carry: list[str] = []
        carry_len = 0
        for sent in reversed(prev_buf):
            if carry_len >= overlap_target:
                break
            carry.insert(0, sent)
            carry_len += len(sent) + 1
        return carry, carry_len, max(cursor - carry_len, 0)

    def _truncate(self, item: tuple[str, int, int]) -> tuple[str, int, int]:
        text, start, end = item
        if len(text) > self._config.max_chars:
            text = text[: self._config.max_chars]
            end = start + len(text)
        return text, start, end


def _split_into_sentences(text: str) -> list[str]:
    """Best-effort sentence split that preserves source whitespace minimally."""
    parts = _SENTENCE_END.split(text)
    return [p.strip() for p in parts if p.strip()]
