"""Tests for FilesystemSampleLoader (M6.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.evaluation.loader import FilesystemSampleLoader


def _write_suite(
    data_dir: Path,
    library_id: str,
    suite: str,
    version: str,
    body: str,
) -> Path:
    suite_dir = data_dir / "libraries" / library_id / "evals"
    suite_dir.mkdir(parents=True, exist_ok=True)
    path = suite_dir / f"{suite}.{version}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


_VALID_SUITE = """\
suite: qa.smoke
suite_version: v1
library_id: lib-x

samples:
  - sample_id: q-001
    question: What is X?
    type: definition
    difficulty: easy
    expected_evidence_doc_ids:
      - doc-001
    expected_key_points:
      - "key one"
    acceptable_score_floor: 0.7
    human_validated: true
    created_by: claude
  - sample_id: q-002
    question: Why Y?
    expected_evidence_doc_ids:
      - doc-002
"""


class TestFilesystemSampleLoaderHappyPath:
    def test_loads_samples_with_top_level_metadata(self, tmp_path: Path) -> None:
        # Arrange
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", _VALID_SUITE)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        # Act
        samples = loader.load_suite("lib-x", "qa.smoke", "v1")

        # Assert
        assert len(samples) == 2
        first = samples[0]
        assert first.sample_id == "q-001"
        assert first.library_id == "lib-x"
        assert first.suite == "qa.smoke"
        assert first.suite_version == "v1"
        assert first.expected_evidence_doc_ids == ("doc-001",)
        assert first.expected_key_points == ("key one",)
        assert first.difficulty == "easy"
        assert first.type == "definition"
        assert first.human_validated is True

    def test_drops_unknown_metadata_fields(self, tmp_path: Path) -> None:
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", _VALID_SUITE)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        samples = loader.load_suite("lib-x", "qa.smoke", "v1")

        # `created_by: claude` is in the YAML but should not surface as an
        # attribute (EvalSample has extra="forbid").
        assert not hasattr(samples[0], "created_by")


class TestFilesystemSampleLoaderErrors:
    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(FileNotFoundError):
            loader.load_suite("lib-x", "qa.smoke", "v1")

    def test_empty_samples_raises_value_error(self, tmp_path: Path) -> None:
        body = "suite: qa.smoke\nsuite_version: v1\nlibrary_id: lib-x\nsamples: []\n"
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", body)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="non-empty 'samples'"):
            loader.load_suite("lib-x", "qa.smoke", "v1")

    def test_doc_id_must_be_non_empty_string(self, tmp_path: Path) -> None:
        body = (
            "suite: qa.smoke\nsuite_version: v1\nlibrary_id: lib-x\n"
            "samples:\n"
            "  - sample_id: q-bad\n"
            "    question: 'huh'\n"
            "    expected_evidence_doc_ids:\n"
            "      - ''\n"
        )
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", body)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="expected_evidence_doc_ids"):
            loader.load_suite("lib-x", "qa.smoke", "v1")

    def test_unknown_sample_field_rejected(self, tmp_path: Path) -> None:
        body = (
            "suite: qa.smoke\nsuite_version: v1\nlibrary_id: lib-x\n"
            "samples:\n"
            "  - sample_id: q-bad\n"
            "    question: 'q'\n"
            "    bogus_field: 1\n"
        )
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", body)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="unknown field"):
            loader.load_suite("lib-x", "qa.smoke", "v1")

    def test_sample_id_required(self, tmp_path: Path) -> None:
        body = (
            "suite: qa.smoke\nsuite_version: v1\nlibrary_id: lib-x\n"
            "samples:\n"
            "  - question: 'no id here'\n"
        )
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", body)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="sample_id"):
            loader.load_suite("lib-x", "qa.smoke", "v1")

    def test_library_id_mismatch_rejected(self, tmp_path: Path) -> None:
        # Place a file under lib-y/ that internally declares library_id: lib-x.
        # The on-disk path matches the caller's request, but the YAML body
        # contradicts it — that mismatch must be rejected.
        _write_suite(tmp_path, "lib-y", "qa.smoke", "v1", _VALID_SUITE)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="library_id mismatch"):
            loader.load_suite("lib-y", "qa.smoke", "v1")

    def test_root_must_be_mapping(self, tmp_path: Path) -> None:
        body = "- not\n- a\n- mapping\n"
        _write_suite(tmp_path, "lib-x", "qa.smoke", "v1", body)
        loader = FilesystemSampleLoader(data_dir=tmp_path)

        with pytest.raises(ValueError, match="must be a mapping"):
            loader.load_suite("lib-x", "qa.smoke", "v1")
