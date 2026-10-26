"""Fixtures for the /api/v1 tests: the seeded e2e catalog plus the invented household of
scripts/make_api_fixtures.py, copied per test, and a client that sends the development token."""

import importlib.util
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import make_settings
from e2e.flows.seed import build
from starlette.testclient import TestClient

from polished.config import Settings
from polished.db import connect
from polished.server import create_app

ROOT = Path(__file__).resolve().parents[1]
DEV_TOKEN = "dev-token-for-tests"
LOOPBACK = ("127.0.0.1", 50000)
NOW = datetime(2026, 10, 26, 16, 30, tzinfo=UTC)  # 17:30 on 2026-10-26 in Warsaw
TODAY = "2026-10-26"


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW


@pytest.fixture
def frozen_today(monkeypatch):
    """The household's today (wear.local_today, which every API date check uses) is TODAY."""
    monkeypatch.setattr("polished.wear.datetime", FrozenDatetime)


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def api_template(tmp_path_factory) -> tuple[Path, dict[str, int]]:
    path = tmp_path_factory.mktemp("api-template") / "template.db"
    build(str(path))
    conn = connect(str(path))
    ids = load_script("make_api_fixtures").add_household(conn)
    conn.execute("pragma wal_checkpoint(truncate)")
    conn.close()
    return path, ids


@dataclass
class Api:
    client: TestClient
    settings: Settings
    ids: dict[str, int]
    template: Path

    def conn(self):
        return connect(self.settings.db_path)

    def get(self, path: str, **kwargs):
        return self.client.get(path, **kwargs)

    def shade(self, title: str) -> int:
        conn = self.conn()
        try:
            return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]
        finally:
            conn.close()

    def count(self, table: str, where: str = "1", *args) -> int:
        conn = self.conn()
        try:
            return conn.execute(f"select count(*) from {table} where {where}", args).fetchone()[0]
        finally:
            conn.close()

    def rows(self, sql: str, *args) -> list[dict]:
        conn = self.conn()
        try:
            return [dict(r) for r in conn.execute(sql, args)]
        finally:
            conn.close()


def assert_error(response, status: int, code: str, field: str | None = None) -> dict:
    """The /api/v1 error body: status, code, a message to show, and `field` when named."""
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    if field is not None:
        assert error["field"] == field
    return error


def make_api(tmp_path, template: Path, ids: dict[str, int], **overrides) -> Api:
    shutil.copy(template, tmp_path / "polished.db")
    settings = make_settings(tmp_path, dev_token=DEV_TOKEN, **overrides)
    client = TestClient(
        create_app(settings),
        base_url=settings.public_url,
        headers={"Authorization": f"Bearer {DEV_TOKEN}"},
        follow_redirects=False,
        client=LOOPBACK,
    )
    return Api(client, settings, ids, template)


@pytest.fixture
def api(tmp_path, api_template, frozen_today) -> Api:
    template, ids = api_template
    return make_api(tmp_path, template, ids)


@pytest.fixture
def bare_client(api) -> TestClient:
    """The same app, but sending no credentials."""
    return TestClient(
        api.client.app,
        base_url=api.settings.public_url,
        follow_redirects=False,
        client=LOOPBACK,
    )
