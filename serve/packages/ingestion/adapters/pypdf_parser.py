"""PDF parser using pypdf — pure Python, no external binaries."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

from packages.core.models import Document
from packages.ingestion.protocols import ParsedDocument, ParsedSection

_MIN_TITLE_LEN = 5
_MAX_TITLE_LEN = 200


class PypdfParser:
    """Parse PDFs page-by-page into ParsedDocument.

    Lightweight: no OCR, no formula reconstruction. For the M1 spike on
    arXiv-style PDFs this suffices. Upgrade to Nougat/MinerU later if
    formula/table fidelity becomes a bottleneck (M2+).
    """

    async def parse(self, library_id: str, file_path: Path) -> ParsedDocument:
        if not file_path.exists():
            msg = f"PDF not found: {file_path}"
            raise FileNotFoundError(msg)

        return await asyncio.to_thread(self._parse_sync, library_id, file_path)

    def _parse_sync(self, library_id: str, file_path: Path) -> ParsedDocument:
        reader = PdfReader(str(file_path))
        sections: list[ParsedSection] = []
        for page_idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            sections.append(ParsedSection(text=text, page=page_idx))

        meta_raw: object = reader.metadata or {}
        title = self._extract_title(meta_raw, file_path, sections)
        authors = self._extract_authors(meta_raw)
        year = self._extract_year(meta_raw)

        content_hash = _sha256_file(file_path)

        document = Document(
            library_id=library_id,
            doc_id=file_path.stem,
            title=title,
            authors=authors,
            year=year,
            venue=None,
            source_url=f"file://{file_path.resolve()}",
            doi=None,
            content_hash=content_hash,
            ingest_ts=datetime.now(UTC),
        )

        return ParsedDocument(document=document, sections=tuple(sections))

    @staticmethod
    def _extract_title(meta: object, file_path: Path, sections: list[ParsedSection]) -> str:
        title = _getattr_or_get(meta, "title")
        if title and isinstance(title, str) and title.strip():
            return title.strip()
        if sections:
            first_line = sections[0].text.split("\n", 1)[0].strip()
            if _MIN_TITLE_LEN <= len(first_line) <= _MAX_TITLE_LEN:
                return first_line
        return file_path.stem

    @staticmethod
    def _extract_authors(meta: object) -> tuple[str, ...]:
        author_str = _getattr_or_get(meta, "author")
        if not isinstance(author_str, str) or not author_str.strip():
            return ()
        parts = [p.strip() for p in author_str.replace(";", ",").split(",")]
        return tuple(p for p in parts if p)

    @staticmethod
    def _extract_year(meta: object) -> int | None:
        creation = _getattr_or_get(meta, "creation_date")
        if isinstance(creation, datetime):
            return creation.year
        return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _getattr_or_get(obj: object, key: str) -> object:
    """Safely fetch an attribute or dict-key value, returning None if missing."""
    if obj is None:
        return None
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        for candidate in (key, f"/{key.title()}", f"/{key}"):
            if candidate in obj:
                return obj[candidate]  # type: ignore[no-any-return]
    return None
