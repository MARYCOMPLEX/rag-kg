"""Base error hierarchy for the entire project.

Each package defines its own errors.py inheriting from these bases.
"""

from __future__ import annotations


class RKBError(Exception):
    """Root exception for all rag-kg-copilot errors."""


class ConfigError(RKBError):
    """Configuration is missing or invalid."""


class LibraryNotFoundError(RKBError):
    """Requested library_id does not exist."""

    def __init__(self, library_id: str) -> None:
        super().__init__(f"Library not found: {library_id}")
        self.library_id = library_id


class LibraryAlreadyExistsError(RKBError):
    """Attempted to create a library that already exists."""

    def __init__(self, library_id: str) -> None:
        super().__init__(f"Library already exists: {library_id}")
        self.library_id = library_id


class CrossLibraryReferenceError(RKBError):
    """Detected an illegal cross-library data reference."""

    def __init__(self, source_library: str, target_library: str) -> None:
        super().__init__(
            f"Cross-library reference from '{source_library}' to '{target_library}' is forbidden"
        )
        self.source_library = source_library
        self.target_library = target_library
