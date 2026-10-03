"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

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
