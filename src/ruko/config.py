"""Typed application settings.

Settings come from environment variables prefixed with ``RUKO_`` (and, for local
development, from a ``.env`` file in the working directory). Secrets are held as
``SecretStr`` so they never appear in reprs or logs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from ruko import __version__

ENV_PREFIX = "RUKO_"
_REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Settings(BaseModel):
    """All runtime configuration for the Ruko backend."""

    app_name: str = "ruko"
    version: str = __version__
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    data_dir: Path = _REPO_DATA_DIR
    # Built frontend (frontend/dist) to serve at "/"; unset means API only.
    static_dir: Path | None = None

    # Unverified facts: shown in development, hidden in production (CLAUDE.md section 3).
    # None means "decide from environment"; set true/false to override.
    show_unverified_facts: bool | None = None

    default_locale: str = "en"
    enabled_locales: list[str] = Field(default_factory=lambda: ["en", "hi", "kn"])

    # LLM provider ("auto" = Gemini when a key is present, otherwise lexicon-only).
    llm_provider: Literal["auto", "gemini", "fake", "none"] = "auto"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    # Used when the main model is out of quota (HTTP 429), so a free-tier daily limit does not
    # silently turn screenshots and voice off. Empty means no fallback.
    gemini_fallback_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: float = 15.0
    llm_max_retries: int = 2
    llm_invalid_output_retries: int = 1

    # Speech providers, tried in this order.
    speech_providers: list[str] = Field(default_factory=lambda: ["sarvam"])
    sarvam_api_key: SecretStr | None = None
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"
    sarvam_tts_max_chars: int = 2500
    speech_timeout_seconds: float = 30.0

    # Input limits.
    max_text_chars: int = 4000
    max_image_bytes: int = 4 * 1024 * 1024
    max_audio_bytes: int = 5 * 1024 * 1024
    max_audio_seconds: float = 30.0
    max_request_bytes: int = 7 * 1024 * 1024

    # HTTP edge.
    cors_allow_origins: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 60

    @property
    def unverified_facts_visible(self) -> bool:
        """True if facts not yet verified by a human may be shown (never in production)."""
        if self.show_unverified_facts is not None:
            return self.show_unverified_facts
        return self.environment != "prod"


_LIST_FIELDS = {"enabled_locales", "speech_providers", "cors_allow_origins"}


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read simple ``KEY=VALUE`` lines from a .env file, ignoring comments."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(
    env: Mapping[str, str] | None = None, dotenv_path: Path | None = None
) -> Settings:
    """Build settings from environment variables (and an optional .env file).

    Args:
        env: Mapping to read from. Defaults to ``os.environ``.
        dotenv_path: Optional .env file; real environment variables win over it.

    Returns:
        A validated ``Settings`` instance.
    """
    source: dict[str, str] = {}
    if dotenv_path is not None:
        source.update(_read_dotenv(dotenv_path))
    source.update(env if env is not None else os.environ)

    raw: dict[str, object] = {}
    for field_name in Settings.model_fields:
        key = ENV_PREFIX + field_name.upper()
        if key not in source or source[key] == "":
            continue
        value: object = source[key]
        if field_name in _LIST_FIELDS:
            value = [item.strip() for item in str(value).split(",") if item.strip()]
        raw[field_name] = value
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings, read once from the environment and ``./.env``."""
    return load_settings(dotenv_path=Path.cwd() / ".env")
