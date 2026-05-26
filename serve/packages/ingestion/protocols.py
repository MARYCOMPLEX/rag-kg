"""Ingestion layer protocol definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import Chunk, Document


class ParsedSection(BaseModel):
    """A logical section of a parsed document (e.g., a page or heading block)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str | None = None
    text: str
    page: int | None = None


class ParsedDocument(BaseModel):
    """Parser output — Document metadata + extracted sections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document: Document
    sections: tuple[ParsedSection, ...] = Field(default_factory=tuple)


@runtime_checkable
class Parser(Protocol):
    """Parse a raw file into a structured document with text sections."""

    async def parse(self, library_id: str, file_path: Path) -> ParsedDocument: ...


@runtime_checkable
class Chunker(Protocol):
    """Split a parsed document into retrieval-sized chunks."""

    def chunk(self, library_id: str, parsed: ParsedDocument) -> list[Chunk]: ...


@runtime_checkable
class Deduper(Protocol):
    """Detect and filter duplicate documents or chunks."""

    async def is_duplicate(self, library_id: str, content_hash: str) -> bool: ...
