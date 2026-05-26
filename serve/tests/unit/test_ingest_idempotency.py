"""Hash helper coverage for ingest idempotency."""

from __future__ import annotations

from packages.ingestion.idempotency import hash_file, short_hash


def test_hash_file_is_deterministic(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    h1 = hash_file(p)
    h2 = hash_file(p)
    assert h1 == h2
    assert len(h1) == 64


def test_hash_file_changes_with_content(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    h1 = hash_file(p)
    p.write_bytes(b"hello world!")
    h2 = hash_file(p)
    assert h1 != h2


def test_short_hash() -> None:
    assert short_hash("abcdef" * 12, 8) == "abcdefab"
