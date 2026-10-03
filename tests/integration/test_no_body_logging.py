"""Proves that request and response bodies never reach the logs."""

import logging

from fastapi import APIRouter
from fastapi.testclient import TestClient

from ruko.main import create_app
from ruko.observability import JsonFormatter, log_event

SENTINEL = "SENTINEL-BODY-CONTENT-90210"


def _all_log_text(records: list[logging.LogRecord]) -> str:
    formatter = JsonFormatter()
    parts = []
    for record in records:
        parts.append(formatter.format(record))
        parts.append(repr(record.__dict__))
    return "\n".join(parts)


def test_bodies_queries_and_paths_are_not_logged(settings, caplog):
    app = create_app(settings)
    router = APIRouter()

    @router.post("/_test/echo")
    def echo(payload: dict) -> dict:
        return {"echo": payload}

    app.include_router(router)
    caplog.set_level(logging.DEBUG)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post("/_test/echo", json={"message": SENTINEL})
        client.post(f"/health?q={SENTINEL}", content=SENTINEL)
        client.get(f"/unknown/{SENTINEL}")
        client.post("/_test/echo", content=SENTINEL, headers={"content-type": "application/json"})

    text = _all_log_text(caplog.records)
    assert "request_completed" in text
    assert SENTINEL not in text


def test_log_event_drops_non_allow_listed_fields(caplog):
    caplog.set_level(logging.INFO)
    log_event("demo", request_id="r1", message_text=SENTINEL, body=SENTINEL, status=200)
    text = _all_log_text(caplog.records)
    assert '"status": 200' in text
    assert SENTINEL not in text
