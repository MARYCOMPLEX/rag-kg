"""Tests for the unified error envelope schema."""

from __future__ import annotations

from packages.core.api_errors import ErrorCode, ErrorEnvelope


class TestErrorCode:
    def test_codes_are_string_valued(self) -> None:
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.LIBRARY_NOT_FOUND.value == "LIBRARY_NOT_FOUND"
        assert ErrorCode.RATE_LIMITED.value == "RATE_LIMITED"

    def test_set_is_stable(self) -> None:
        """Adding new codes is fine; removing/renaming would break the wire contract."""
        expected = {
            "VALIDATION_ERROR",
            "AUTH_ERROR",
            "NOT_FOUND",
            "LIBRARY_NOT_FOUND",
            "LIBRARY_ALREADY_EXISTS",
            "CONFLICT",
            "RATE_LIMITED",
            "UPSTREAM_ERROR",
            "INTERNAL_ERROR",
        }
        assert expected.issubset({c.value for c in ErrorCode})


class TestErrorEnvelope:
    def test_round_trip(self) -> None:
        env = ErrorEnvelope(
            code=ErrorCode.NOT_FOUND,
            message="Library missing",
            request_id="abc123",
            details={"library_id": "demo"},
        )
        assert env.message == "Library missing"
        assert env.code == ErrorCode.NOT_FOUND

    def test_dump_json_serializes_enum(self) -> None:
        env = ErrorEnvelope(
            code=ErrorCode.VALIDATION_ERROR,
            message="bad",
            request_id="rid",
        )
        dumped = env.model_dump(mode="json")
        assert dumped["code"] == "VALIDATION_ERROR"
        assert dumped["request_id"] == "rid"
        assert dumped["details"] is None
