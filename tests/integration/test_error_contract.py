from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from ruko.errors import ERROR_SPECS, ErrorCode, ErrorResponse, RukoError
from ruko.main import create_app

SECRET = "SENTINEL-MESSAGE-TEXT-7731"


def _assert_contract(body: dict, code: ErrorCode) -> None:
    ErrorResponse.model_validate(body)
    error = body["error"]
    assert error["code"] == code.value
    assert error["message_key"] == f"error.{code.value.lower()}"
    assert error["retryable"] is ERROR_SPECS[code].retryable


def test_unknown_route_uses_error_contract(client):
    response = client.get("/nope")
    assert response.status_code == 404
    _assert_contract(response.json(), ErrorCode.NOT_FOUND)


def test_wrong_method_uses_error_contract(client):
    response = client.post("/health", json={"x": 1})
    assert response.status_code == 405
    _assert_contract(response.json(), ErrorCode.METHOD_NOT_ALLOWED)


class _Echo(BaseModel):
    text: str
    count: int


def _app_with_test_routes(settings):
    app = create_app(settings)
    router = APIRouter()

    @router.post("/_test/validate")
    def validate(payload: _Echo) -> dict:
        return {"ok": True}

    @router.get("/_test/ruko-error")
    def ruko_error() -> dict:
        raise RukoError(ErrorCode.LLM_UNAVAILABLE)

    @router.get("/_test/crash")
    def crash() -> dict:
        raise ValueError(SECRET)

    app.include_router(router)
    return app


def test_validation_error_never_echoes_input(settings):
    with TestClient(_app_with_test_routes(settings)) as client:
        response = client.post("/_test/validate", json={"text": SECRET, "count": "not-a-number"})
    assert response.status_code == 422
    body = response.json()
    _assert_contract(body, ErrorCode.INVALID_REQUEST)
    assert body["error"]["fields"] == ["body.count"]
    assert SECRET not in response.text


def test_typed_error_maps_to_status_and_retryable(settings):
    with TestClient(_app_with_test_routes(settings)) as client:
        response = client.get("/_test/ruko-error")
    assert response.status_code == 503
    _assert_contract(response.json(), ErrorCode.LLM_UNAVAILABLE)


def test_unexpected_error_hides_exception_message(settings):
    with TestClient(_app_with_test_routes(settings), raise_server_exceptions=False) as client:
        response = client.get("/_test/crash")
    assert response.status_code == 500
    _assert_contract(response.json(), ErrorCode.INTERNAL_ERROR)
    assert SECRET not in response.text


def test_every_error_code_has_a_spec():
    assert set(ERROR_SPECS) == set(ErrorCode)
