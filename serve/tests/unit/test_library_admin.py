"""Tests for library admin helper."""

from __future__ import annotations

import pytest

from packages.core.library_admin import LibraryAware, init_library, purge_library


class FakeAdapter:
    """Test double that records init/purge calls."""

    def __init__(self) -> None:
        self.inited: list[str] = []
        self.purged: list[str] = []

    async def init_library(self, library_id: str) -> None:
        self.inited.append(library_id)

    async def purge_library(self, library_id: str) -> None:
        self.purged.append(library_id)


class TestLibraryAdmin:
    def test_fake_adapter_implements_protocol(self) -> None:
        adapter = FakeAdapter()
        assert isinstance(adapter, LibraryAware)

    @pytest.mark.asyncio
    async def test_init_library_calls_all_adapters(self) -> None:
        a = FakeAdapter()
        b = FakeAdapter()

        await init_library("my-lib", adapters=[a, b])

        assert a.inited == ["my-lib"]
        assert b.inited == ["my-lib"]

    @pytest.mark.asyncio
    async def test_purge_library_calls_all_adapters(self) -> None:
        a = FakeAdapter()
        b = FakeAdapter()

        await purge_library("my-lib", adapters=[a, b])

        assert a.purged == ["my-lib"]
        assert b.purged == ["my-lib"]

    @pytest.mark.asyncio
    async def test_init_library_with_empty_adapters(self) -> None:
        await init_library("my-lib", adapters=[])

    @pytest.mark.asyncio
    async def test_purge_library_with_empty_adapters(self) -> None:
        await purge_library("my-lib", adapters=[])
