"""P8: the backend serves the built frontend, without ever letting it shadow the API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ruko.config import Settings, load_settings
from ruko.main import create_app

INDEX = "<!doctype html><title>Ruko</title><div id='root'></div>"


@pytest.fixture
def build(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "app-1a2b.js").write_text("console.log('app')", encoding="utf-8")
    (tmp_path / "sw.js").write_text("// worker", encoding="utf-8")
    (tmp_path / "manifest.webmanifest").write_text('{"name":"Ruko"}', encoding="utf-8")
    return tmp_path


def client_for(static_dir: Path | None) -> TestClient:
    settings = Settings(
        environment="test", llm_provider="fake", speech_providers=["fake"], static_dir=static_dir
    )
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_without_a_build_it_is_api_only(tmp_path):
    for client in (client_for(None), client_for(tmp_path)):  # unset, and a folder with no index
        assert client.get("/health").status_code == 200
        response = client.get("/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_the_page_is_served_at_root_and_never_cached(build):
    response = client_for(build).get("/")
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-eval" not in csp


def test_app_routes_get_the_page_so_a_reload_or_share_link_works(build):
    client = client_for(build)
    for path in ("/demo/broker", "/anything/else", "/?text=Guaranteed%203x"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text == INDEX, path


def test_hashed_assets_are_immutable_but_the_worker_and_manifest_are_not_cached(build):
    client = client_for(build)
    asset = client.get("/assets/app-1a2b.js")
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "content-security-policy" not in asset.headers
    worker = client.get("/sw.js")
    assert worker.status_code == 200
    assert worker.headers["cache-control"] == "no-cache"
    manifest = client.get("/manifest.webmanifest")
    assert manifest.headers["cache-control"] == "no-cache"
    assert manifest.headers["content-type"].startswith("application/manifest+json")


def test_a_missing_file_is_a_404_not_the_page(build):
    client = client_for(build)
    for path in ("/assets/missing.js", "/nothing.png"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert INDEX not in response.text


def test_the_api_always_wins(build):
    client = client_for(build)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    unknown = client.get("/v1/does-not-exist")
    assert unknown.status_code == 404
    assert unknown.headers["content-type"].startswith("application/json")
    assert unknown.json()["error"]["code"] == "NOT_FOUND"
    posted = client.post(
        "/v1/analyze",
        json={"input": {"type": "text", "content": "What is an IPO?"}, "locale": "en"},
    )
    assert posted.status_code == 200
    assert posted.json()["kind"] == "glossary"


def test_the_setting_is_read_from_the_environment(build):
    settings = load_settings({"RUKO_STATIC_DIR": str(build)})
    assert settings.static_dir == build
    assert load_settings({}).static_dir is None
