import base64
import copy
import json
import os
import socket
from pathlib import Path

import itsdangerous
import pytest
from fastapi.testclient import TestClient

from polished.config import Settings
from polished.db import connect
from polished.migrate import MIGRATIONS, migrate
from polished.server import create_app

LOCAL_URL = "http://localhost:8080"
OIDC_URL = "https://polished.example.test"
SECRET = "test-secret-test-secret-test-secret-0"
FIXTURES = Path(__file__).parent / "fixtures"


def migrations_below(tmp_path: Path, version: int) -> Path:
    """A copy of the packaged migrations with a number under `version`, to build an older database."""
    directory = tmp_path / f"migrations-below-{version}"
    directory.mkdir()
    for path in MIGRATIONS.iterdir():
        if path.name.endswith(".sql") and int(path.name[:3]) < version:
            (directory / path.name).write_text(path.read_text())
    return directory


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """A developer's POLISHED_* variables must not change what the tests see."""
    for name in list(os.environ):
        if name.startswith("POLISHED_"):
            monkeypatch.delenv(name)


@pytest.fixture(autouse=True)
def no_colour_pause(monkeypatch):
    """The colour step waits between CDN downloads; tests never wait."""
    monkeypatch.setattr("polished.catalog.colour.CDN_INTERVAL_S", 0)


@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch):
    """Anything that tries to open an internet socket or resolve a name fails the test."""

    def refuse(*args, **kwargs):
        raise RuntimeError("outbound network access is blocked in tests")

    real_connect = socket.socket.connect

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            refuse()
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", lambda self, address: refuse())
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "db_path": str(tmp_path / "polished.db"),
        "public_url": LOCAL_URL,
        "auth_mode": "none",
        "session_secret": SECRET,
        "sync_enabled": False,
        "release_sheet_url": "",  # the release sheet is a second request; its tests switch it on
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def oidc_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "public_url": OIDC_URL,
        "auth_mode": "oidc",
        "oidc_client_id": "client-id",
        "oidc_client_secret": "client-secret",
    }
    values.update(overrides)
    return make_settings(tmp_path, **values)


def make_client(settings: Settings) -> TestClient:
    """Migrated database, and default headers that include the Origin (as a browser sends it)."""
    migrate(settings.db_path)
    return TestClient(
        create_app(settings),
        base_url=settings.public_url,
        headers={"Origin": settings.public_url},
        follow_redirects=False,
    )


def session_cookie(settings: Settings, data: dict) -> str:
    """A session cookie signed like Starlette's SessionMiddleware does."""
    signer = itsdangerous.TimestampSigner(settings.session_secret.get_secret_value())
    return signer.sign(base64.b64encode(json.dumps(data).encode())).decode()


def read_session(settings: Settings, cookie: str) -> dict:
    signer = itsdangerous.TimestampSigner(settings.session_secret.get_secret_value())
    return json.loads(base64.b64decode(signer.unsign(cookie)))


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings) -> TestClient:
    """AUTH_MODE=none app on localhost."""
    return make_client(settings)


@pytest.fixture
def oidc_app_settings(tmp_path) -> Settings:
    return oidc_settings(tmp_path)


@pytest.fixture
def oidc_client(oidc_app_settings) -> TestClient:
    """AUTH_MODE=oidc app; nobody is signed in."""
    return make_client(oidc_app_settings)


class FakeClock:
    """A monotonic clock whose sleep() advances it instead of waiting."""

    def __init__(self):
        self.time = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.time

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds


def load_feed() -> list[dict]:
    """The products of tests/fixtures/feed_trimmed.json (a fresh copy every call)."""
    return json.loads((FIXTURES / "feed_trimmed.json").read_text(encoding="utf-8"))["products"]


def synthetic_products(count: int, start: int = 0) -> list[dict]:
    """`count` distinct shade-like products, for tests that need full 250-product pages."""
    template = next(p for p in load_feed() if p["handle"] == "thirst-trap")
    products = []
    for number in range(start, start + count):
        product = copy.deepcopy(template)
        product["id"] = 9_000_000_000 + number
        product["handle"] = f"synthetic-{number}"
        product["title"] = f"Synthetic {number}"
        product["variants"][0]["id"] = 8_000_000_000 + number
        product["variants"][0]["sku"] = f"HL-{number:05d}-NP"
        products.append(product)
    return products


@pytest.fixture
def feed() -> list[dict]:
    return load_feed()


@pytest.fixture
def conn(settings):
    """A migrated database, opened the way the app opens it."""
    migrate(settings.db_path)
    connection = connect(settings.db_path)
    yield connection
    connection.close()
