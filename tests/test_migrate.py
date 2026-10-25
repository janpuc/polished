import sqlite3

import pytest

from polished.migrate import MIGRATIONS, migrate

CATALOG_TABLES = {"product", "shade", "shade_alias", "shade_tag", "sync_run"}
CATALOG_INDEXES = {
    "product_handle",
    "product_role",
    "shade_kind",
    "shade_sku",
    "shade_handle",
    "shade_alias_shade",
    "shade_tag_lookup",
}


def names(db_path: str, kind: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "select name from sqlite_master where type = ? and name not like 'sqlite_%'", (kind,)
        )
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_migrations_apply_once_and_a_second_run_applies_nothing(tmp_path):
    db = str(tmp_path / "polished.db")
    assert migrate(db) == ["001_catalog.sql"]
    assert migrate(db) == []
    conn = sqlite3.connect(db)
    assert conn.execute("select version, name from schema_version").fetchall() == [
        (1, "001_catalog.sql")
    ]
    conn.close()


def test_001_catalog_creates_the_tables_of_design_4_1(tmp_path):
    db = str(tmp_path / "polished.db")
    migrate(db)
    assert names(db, "table") >= CATALOG_TABLES
    assert names(db, "index") >= CATALOG_INDEXES


def test_001_catalog_enforces_the_role_check(tmp_path):
    db = str(tmp_path / "polished.db")
    migrate(db)
    conn = sqlite3.connect(db)
    insert = (
        "insert into product (shopify_product_id, variant_id, handle, title, product_type, role,"
        " available, tags_json, raw_json, content_hash, last_seen)"
        " values (1, 1, 'h', 't', 'p', ?, 1, '[]', '{}', 'x', 'now')"
    )
    conn.execute(insert, ("shade",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert.replace("(1, 1,", "(2, 2,"), ("gift",))
    conn.close()


def test_only_the_new_file_runs_when_a_migration_is_added(tmp_path):
    db = str(tmp_path / "polished.db")
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "001_a.sql").write_text("create table a (id integer primary key);")
    assert migrate(db, directory) == ["001_a.sql"]
    (directory / "002_b.sql").write_text("create table b (id integer primary key);")
    assert migrate(db, directory) == ["002_b.sql"]
    assert {"a", "b"} <= names(db, "table")


def test_a_failing_migration_leaves_nothing_behind(tmp_path):
    db = str(tmp_path / "polished.db")
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "001_bad.sql").write_text("create table a (id integer);\nselect * from missing;")
    with pytest.raises(sqlite3.OperationalError):
        migrate(db, directory)
    assert "a" not in names(db, "table")
    conn = sqlite3.connect(db)
    assert conn.execute("select count(*) from schema_version").fetchone() == (0,)
    conn.close()


def test_package_ships_the_migrations():
    assert [p.name for p in MIGRATIONS.iterdir() if p.name.endswith(".sql")] == ["001_catalog.sql"]
