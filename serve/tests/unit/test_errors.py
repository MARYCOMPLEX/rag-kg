"""Tests for error hierarchy."""

from __future__ import annotations

from packages.core.errors import (
    ConfigError,
    CrossLibraryReferenceError,
    LibraryAlreadyExistsError,
    LibraryNotFoundError,
    RKBError,
)


class TestErrorHierarchy:
    def test_all_errors_inherit_from_rkb_error(self) -> None:
        assert issubclass(ConfigError, RKBError)
        assert issubclass(LibraryNotFoundError, RKBError)
        assert issubclass(LibraryAlreadyExistsError, RKBError)
        assert issubclass(CrossLibraryReferenceError, RKBError)

    def test_library_not_found_contains_id(self) -> None:
        err = LibraryNotFoundError("my-lib")
        assert err.library_id == "my-lib"
        assert "my-lib" in str(err)

    def test_library_already_exists_contains_id(self) -> None:
        err = LibraryAlreadyExistsError("my-lib")
        assert err.library_id == "my-lib"
        assert "my-lib" in str(err)

    def test_cross_library_reference_contains_both_ids(self) -> None:
        err = CrossLibraryReferenceError("lib-a", "lib-b")
        assert err.source_library == "lib-a"
        assert err.target_library == "lib-b"
        assert "lib-a" in str(err)
        assert "lib-b" in str(err)
