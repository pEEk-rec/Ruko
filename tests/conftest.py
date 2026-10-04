"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ruko.config import Settings
from ruko.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", llm_provider="fake", speech_providers=["fake"])


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _clear_fact_caches() -> None:
    from ruko.engine.base_rates import load_base_rates
    from ruko.recovery.guide import recovery_routes

    load_base_rates.cache_clear()
    recovery_routes.cache_clear()


@pytest.fixture
def unverified_facts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run a test against a copy of ``data/`` in which no fact is verified by a human.

    The real data now has verified facts, but the rules about unverified ones (hidden in
    production, flagged in ``meta.unverified_fact_ids``) must keep being tested.
    """
    from ruko import data_files

    copy = tmp_path / "data"
    shutil.copytree(data_files.data_dir(), copy)
    for path in (copy / "facts").glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("verified_by_human: true", "verified_by_human: false"), encoding="utf-8"
        )
    monkeypatch.setattr(data_files, "data_dir", lambda: copy)
    _clear_fact_caches()
    yield copy
    monkeypatch.undo()
    _clear_fact_caches()
