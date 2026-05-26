"""Tests for FilesystemLibraryRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps._shared.persistence.library_fs import (
    FilesystemLibraryRepository,
    make_library,
)
from packages.core.errors import LibraryAlreadyExistsError, LibraryNotFoundError


@pytest.fixture
def tmp_repo(tmp_path: Path) -> FilesystemLibraryRepository:
    return FilesystemLibraryRepository(data_dir=tmp_path)


class TestMakeLibrary:
    def test_valid_library_id(self) -> None:
        lib = make_library(library_id="my-lib", name="Test")
        assert lib.library_id == "my-lib"
        assert lib.created_at.tzinfo is not None

    def test_invalid_library_id_uppercase(self) -> None:
        with pytest.raises(ValueError, match="Invalid library_id"):
            make_library(library_id="MyLib", name="Bad")

    def test_invalid_library_id_too_short(self) -> None:
        with pytest.raises(ValueError, match="Invalid library_id"):
            make_library(library_id="ab", name="Bad")

    def test_invalid_library_id_underscore(self) -> None:
        with pytest.raises(ValueError, match="Invalid library_id"):
            make_library(library_id="my_lib", name="Bad")


class TestFilesystemLibraryRepository:
    @pytest.mark.asyncio
    async def test_create_then_get(self, tmp_repo: FilesystemLibraryRepository) -> None:
        lib = make_library(library_id="my-lib", name="My Library", description="desc")
        await tmp_repo.create(lib)

        fetched = await tmp_repo.get("my-lib")
        assert fetched is not None
        assert fetched.library_id == "my-lib"
        assert fetched.name == "My Library"
        assert fetched.description == "desc"

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, tmp_repo: FilesystemLibraryRepository) -> None:
        lib = make_library(library_id="my-lib", name="My Library")
        await tmp_repo.create(lib)
        with pytest.raises(LibraryAlreadyExistsError):
            await tmp_repo.create(lib)

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, tmp_repo: FilesystemLibraryRepository) -> None:
        result = await tmp_repo.get("not-here")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_empty(self, tmp_repo: FilesystemLibraryRepository) -> None:
        assert await tmp_repo.list_all() == []

    @pytest.mark.asyncio
    async def test_list_all_returns_sorted(self, tmp_repo: FilesystemLibraryRepository) -> None:
        await tmp_repo.create(make_library(library_id="zebra", name="Z"))
        await tmp_repo.create(make_library(library_id="alpha", name="A"))
        libs = await tmp_repo.list_all()
        assert [lib.library_id for lib in libs] == ["alpha", "zebra"]

    @pytest.mark.asyncio
    async def test_delete_removes_directory(
        self, tmp_repo: FilesystemLibraryRepository, tmp_path: Path
    ) -> None:
        lib = make_library(library_id="my-lib", name="X")
        await tmp_repo.create(lib)
        assert (tmp_path / "libraries" / "my-lib").exists()
        await tmp_repo.delete("my-lib")
        assert not (tmp_path / "libraries" / "my-lib").exists()

    @pytest.mark.asyncio
    async def test_delete_missing_raises(self, tmp_repo: FilesystemLibraryRepository) -> None:
        with pytest.raises(LibraryNotFoundError):
            await tmp_repo.delete("not-here")

    @pytest.mark.asyncio
    async def test_create_creates_corpus_and_evals_dirs(
        self, tmp_repo: FilesystemLibraryRepository, tmp_path: Path
    ) -> None:
        lib = make_library(library_id="my-lib", name="X")
        await tmp_repo.create(lib)
        base = tmp_path / "libraries" / "my-lib"
        assert (base / "corpus" / "spike").is_dir()
        assert (base / "corpus" / "full").is_dir()
        assert (base / "evals").is_dir()
        assert (base / "meta.yaml").is_file()

    @pytest.mark.asyncio
    async def test_exists(self, tmp_repo: FilesystemLibraryRepository) -> None:
        await tmp_repo.create(make_library(library_id="my-lib", name="X"))
        assert await tmp_repo.exists("my-lib") is True
        assert await tmp_repo.exists("not-here") is False

    @pytest.mark.asyncio
    async def test_meta_yaml_roundtrip_preserves_optional_fields(
        self, tmp_repo: FilesystemLibraryRepository
    ) -> None:
        lib = make_library(
            library_id="my-lib",
            name="X",
            description="desc",
            created_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
        await tmp_repo.create(lib)
        fetched = await tmp_repo.get("my-lib")
        assert fetched is not None
        assert fetched.description == "desc"
