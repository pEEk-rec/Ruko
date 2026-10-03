from ruko import __version__


def test_health_returns_status_and_version_only(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_every_response_carries_a_request_id(client):
    response = client.get("/health")
    assert len(response.headers["x-request-id"]) >= 8


def test_valid_client_request_id_is_echoed(client):
    response = client.get("/health", headers={"x-request-id": "abc12345-test"})
    assert response.headers["x-request-id"] == "abc12345-test"


def test_unsafe_client_request_id_is_replaced(client):
    response = client.get("/health", headers={"x-request-id": "bad id\nwith newline"})
    assert response.headers["x-request-id"] != "bad id\nwith newline"
