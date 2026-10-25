import socket

import pytest
from conftest import make_settings
from fastapi.testclient import TestClient

from polished.server import create_app


def test_healthz_reports_status_version_and_schema(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "dev", "schema": 3}


def test_healthz_on_a_database_that_was_never_migrated_reports_schema_0(tmp_path):
    settings = make_settings(tmp_path)
    client = TestClient(create_app(settings), base_url=settings.public_url)
    assert client.get("/healthz").json()["schema"] == 0


def test_healthz_is_503_when_the_database_cannot_be_opened(tmp_path):
    settings = make_settings(tmp_path, db_path=str(tmp_path / "missing" / "polished.db"))
    client = TestClient(create_app(settings), base_url=settings.public_url)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "error"}


def test_the_test_suite_cannot_open_internet_sockets():
    with pytest.raises(RuntimeError, match="outbound network"):
        socket.create_connection(("holotaco.com", 443))
    with pytest.raises(RuntimeError, match="outbound network"):
        socket.getaddrinfo("holotaco.com", 443)
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(RuntimeError, match="outbound network"),
    ):
        sock.connect(("93.184.216.34", 80))
