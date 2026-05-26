"""Persistence adapters for cross-cutting concerns (library metadata, etc.)."""

from apps._shared.persistence.library_fs import FilesystemLibraryRepository

__all__ = ["FilesystemLibraryRepository"]
