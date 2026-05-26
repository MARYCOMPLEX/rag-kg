"""L1: Document ingestion — parsing, chunking, deduplication."""

from packages.ingestion.adapters.pypdf_parser import PypdfParser
from packages.ingestion.adapters.sentence_chunker import (
    SentenceChunker,
    SentenceChunkerConfig,
)
from packages.ingestion.extractor import (
    LIMITS,
    ExtractionError,
    ExtractionLimits,
    ExtractionReport,
    ExtractionTimeoutError,
    Rejection,
    TooManyFilesError,
    ZipBombError,
    ZipTooLargeError,
    discover_pdfs,
    extract_zip,
    walk_folder,
)
from packages.ingestion.protocols import (
    Chunker,
    Deduper,
    ParsedDocument,
    ParsedSection,
    Parser,
)

__all__ = [
    "LIMITS",
    "Chunker",
    "Deduper",
    "ExtractionError",
    "ExtractionLimits",
    "ExtractionReport",
    "ExtractionTimeoutError",
    "ParsedDocument",
    "ParsedSection",
    "Parser",
    "PypdfParser",
    "Rejection",
    "SentenceChunker",
    "SentenceChunkerConfig",
    "TooManyFilesError",
    "ZipBombError",
    "ZipTooLargeError",
    "discover_pdfs",
    "extract_zip",
    "walk_folder",
]
