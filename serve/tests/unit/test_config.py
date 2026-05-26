"""Tests for configuration management."""

from __future__ import annotations

from packages.core.config import Settings, get_settings


class TestSettings:
    def test_defaults_are_valid(self) -> None:
        settings = Settings()
        assert settings.postgres_url.startswith("postgresql")
        assert settings.qdrant_url.startswith("http")
        assert settings.log_level == "INFO"
        assert settings.debug is False

    def test_llm_timeout_has_bounds(self) -> None:
        settings = Settings()
        assert settings.llm_timeout_s >= 1
        assert settings.llm_timeout_s <= 600

    def test_get_settings_returns_instance(self) -> None:
        settings = get_settings()
        assert isinstance(settings, Settings)
