"""Filesystem-backed loader for eval suite YAML files.

Reads `data/libraries/<library_id>/evals/<suite>.<version>.yaml` and yields
a list of `EvalSample`. Top-level fields (`library_id`, `suite`, `suite_version`)
are merged into each sample so the YAML stays DRY.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast

import yaml

from packages.evaluation.protocols import EvalSample

_DEFAULT_DATA_DIR: Final[Path] = Path("data")
_LIBRARIES_SUBDIR: Final[str] = "libraries"
_EVALS_SUBDIR: Final[str] = "evals"

# Whitelisted EvalSample field names — any other key in YAML is a hard error.
_SAMPLE_FIELDS: Final[frozenset[str]] = frozenset(EvalSample.model_fields.keys())

# Curation metadata permitted at the sample level. EvalSample uses
# extra="forbid", so these keys are silently dropped before construction.
_SAMPLE_METADATA_KEYS: Final[frozenset[str]] = frozenset({"created_by", "notes"})


class FilesystemSampleLoader:
    """`SampleLoader` Protocol impl — reads YAML eval suites from disk."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir if data_dir is not None else _DEFAULT_DATA_DIR

    def load_suite(self, library_id: str, suite: str, version: str) -> list[EvalSample]:
        suite_path = self._suite_path(library_id, suite, version)
        if not suite_path.exists():
            msg = f"Eval suite YAML not found: {suite_path}"
            raise FileNotFoundError(msg)

        raw_root = self._read_yaml(suite_path)
        root = _as_str_keyed_mapping(raw_root, suite_path)

        self._validate_top_level_consistency(
            root, library_id=library_id, suite=suite, version=version, source=suite_path
        )

        samples_node = root.get("samples")
        if not isinstance(samples_node, list) or not samples_node:
            msg = f"Eval suite YAML must define a non-empty 'samples' list: {suite_path}"
            raise ValueError(msg)

        samples_list: list[object] = cast("list[object]", samples_node)
        return [
            self._build_sample(
                entry,
                index=idx,
                library_id=library_id,
                suite=suite,
                suite_version=version,
                source=suite_path,
            )
            for idx, entry in enumerate(samples_list)
        ]

    # --- internals ---------------------------------------------------------

    def _suite_path(self, library_id: str, suite: str, version: str) -> Path:
        return (
            self._data_dir
            / _LIBRARIES_SUBDIR
            / library_id
            / _EVALS_SUBDIR
            / f"{suite}.{version}.yaml"
        )

    @staticmethod
    def _read_yaml(path: Path) -> object:
        with path.open("r", encoding="utf-8") as handle:
            loaded: object = yaml.safe_load(handle)
        return loaded

    @staticmethod
    def _validate_top_level_consistency(
        root: dict[str, object],
        *,
        library_id: str,
        suite: str,
        version: str,
        source: Path,
    ) -> None:
        FilesystemSampleLoader._require_match(
            root.get("library_id"), library_id, "library_id", source
        )
        FilesystemSampleLoader._require_match(root.get("suite"), suite, "suite", source)
        FilesystemSampleLoader._require_match(
            root.get("suite_version"), version, "suite_version", source
        )

    @staticmethod
    def _require_match(declared: object, requested: str, field: str, source: Path) -> None:
        if declared is None:
            return
        if declared != requested:
            msg = (
                f"{field} mismatch in {source}: requested {requested!r}, file declares {declared!r}"
            )
            raise ValueError(msg)

    @staticmethod
    def _build_sample(
        entry: object,
        *,
        index: int,
        library_id: str,
        suite: str,
        suite_version: str,
        source: Path,
    ) -> EvalSample:
        sample_dict = _as_str_keyed_mapping_or_none(entry)
        if sample_dict is None:
            msg = f"Sample #{index} in {source} must be a mapping, got {type(entry).__name__}"
            raise ValueError(msg)

        sample_id_raw = sample_dict.get("sample_id")
        if not isinstance(sample_id_raw, str) or not sample_id_raw:
            msg = f"Sample #{index} in {source} is missing a non-empty 'sample_id'"
            raise ValueError(msg)

        FilesystemSampleLoader._validate_doc_ids(
            sample_dict.get("expected_evidence_doc_ids"), sample_id_raw, source
        )

        payload = FilesystemSampleLoader._project_sample_fields(sample_dict, sample_id_raw, source)
        payload["library_id"] = library_id
        payload["suite"] = suite
        payload["suite_version"] = suite_version
        payload["sample_id"] = sample_id_raw

        try:
            return EvalSample.model_validate(payload)
        except Exception as exc:  # re-raise as ValueError with context
            msg = f"Sample {sample_id_raw!r} in {source} failed validation: {exc}"
            raise ValueError(msg) from exc

    @staticmethod
    def _validate_doc_ids(value: object, sample_id: str, source: Path) -> None:
        if value is None:
            return
        if not isinstance(value, list):
            msg = (
                f"Sample {sample_id!r} in {source}: 'expected_evidence_doc_ids' "
                f"must be a list of strings"
            )
            raise ValueError(msg)
        items: list[object] = cast("list[object]", value)
        for item in items:
            if not isinstance(item, str) or not item:
                msg = (
                    f"Sample {sample_id!r} in {source}: every "
                    f"'expected_evidence_doc_ids' entry must be a non-empty string"
                )
                raise ValueError(msg)

    @staticmethod
    def _project_sample_fields(
        entry: dict[str, object], sample_id: str, source: Path
    ) -> dict[str, object]:
        """Project YAML keys onto EvalSample fields; reject unknown keys."""
        payload: dict[str, object] = {}
        for key, raw_value in entry.items():
            if key in _SAMPLE_METADATA_KEYS:
                continue
            if key not in _SAMPLE_FIELDS:
                msg = (
                    f"Sample {sample_id!r} in {source}: unknown field {key!r} "
                    f"(allowed: {sorted(_SAMPLE_FIELDS)})"
                )
                raise ValueError(msg)
            payload[key] = raw_value
        return payload


def _as_str_keyed_mapping(value: object, source: Path) -> dict[str, object]:
    result = _as_str_keyed_mapping_or_none(value)
    if result is None:
        msg = f"Eval suite YAML root must be a mapping: {source}"
        raise ValueError(msg)
    return result


def _as_str_keyed_mapping_or_none(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    raw_dict = cast("dict[object, object]", value)
    out: dict[str, object] = {}
    for k, v in raw_dict.items():
        if not isinstance(k, str):
            return None
        out[k] = v
    return out


__all__ = ["FilesystemSampleLoader"]
