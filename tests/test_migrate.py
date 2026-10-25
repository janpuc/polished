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
    assert migrate(db) == [
        "001_catalog.sql",
        "002_inventory.sql",
        "003_identifiers.sql",
        "004_wheels_stacks.sql",
        "005_swatch_image.sql",
        "006_swatch_colour.sql",
    ]
    assert migrate(db) == []
    conn = sqlite3.connect(db)
    assert conn.execute("select version, name from schema_version").fetchall() == [
        (1, "001_catalog.sql"),
        (2, "002_inventory.sql"),
        (3, "003_identifiers.sql"),
        (4, "004_wheels_stacks.sql"),
        (5, "005_swatch_image.sql"),
        (6, "006_swatch_colour.sql"),
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
    assert sorted(p.name for p in MIGRATIONS.iterdir() if p.name.endswith(".sql")) == [
        "001_catalog.sql",
        "002_inventory.sql",
        "003_identifiers.sql",
        "004_wheels_stacks.sql",
        "005_swatch_image.sql",
        "006_swatch_colour.sql",
    ]


def test_002_inventory_applies_on_top_of_a_synced_001_database(tmp_path):
    from conftest import load_feed
    from shade_data import apply

    from polished.db import connect

    db = str(tmp_path / "polished.db")
    only_001 = tmp_path / "only_001"
    only_001.mkdir()
    # 005 rides along because the sync writes shade.swatch_image_url.
    for name in ("001_catalog.sql", "005_swatch_image.sql"):
        (only_001 / name).write_text((MIGRATIONS / name).read_text())
    assert migrate(db, only_001) == ["001_catalog.sql", "005_swatch_image.sql"]
    conn = connect(db)
    apply(conn, load_feed())
    shades = conn.execute("select count(*) from shade").fetchone()[0]
    assert shades == 9
    assert "bottle" not in names(db, "table")

    assert migrate(db) == [
        "002_inventory.sql",
        "003_identifiers.sql",
        "004_wheels_stacks.sql",
        "006_swatch_colour.sql",
    ]
    assert names(db, "table") >= {"bottle", "wishlist_item"}
    assert names(db, "index") >= {"bottle_shade", "bottle_printed_code"}
    assert "shade_status" in names(db, "view")
    assert conn.execute("select count(*) from shade").fetchone()[0] == shades
    status = conn.execute("select * from shade_status").fetchall()
    assert len(status) == shades
    assert {(r["owned_count"], r["bottle_count"], r["wishlisted"]) for r in status} == {(0, 0, 0)}

    conn.execute("insert into bottle (shade_id) values (1)")
    conn.execute("insert into wishlist_item (shade_id) values (2)")
    assert conn.execute("select state, archived from bottle").fetchone()[:] == ("full", 0)
    assert (
        conn.execute("select owned_count from shade_status where shade_id = 1").fetchone()[0] == 1
    )
    assert conn.execute("select wishlisted from shade_status where shade_id = 2").fetchone()[0] == 1
    conn.close()
    assert migrate(db) == []


def test_002_inventory_enforces_its_checks(tmp_path):
    db = str(tmp_path / "polished.db")
    migrate(db)
    conn = sqlite3.connect(db)
    conn.execute("pragma foreign_keys = on")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into bottle (shade_id) values (1)")  # no such shade
    conn.close()


def test_003_identifiers_keeps_one_mapping_per_code_and_follows_its_shade(tmp_path):
    from polished.db import connect

    db = str(tmp_path / "polished.db")
    migrate(db)
    assert "shade_identifier" in names(db, "table")
    assert "shade_identifier_shade" in names(db, "index")
    conn = connect(db)
    conn.execute(
        "insert into shade (source, kind, title, search_text) values ('manual', 'polish', 'A', 'a')"
    )
    insert = "insert into shade_identifier (kind, value, shade_id) values (?, ?, 1)"
    conn.execute(insert, ("gtin", "0810170284120"))
    row = conn.execute("select source, use_count, last_used_at from shade_identifier").fetchone()
    assert tuple(row) == ("learned", 0, None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("gtin", "0810170284120"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("sku", "HL-1"))
    conn.execute("delete from shade where id = 1")
    assert conn.execute("select count(*) from shade_identifier").fetchone()[0] == 0
    conn.close()


def test_004_applies_on_top_of_001_to_003_and_creates_the_wheel_tables(tmp_path):
    db = str(tmp_path / "polished.db")
    directory = tmp_path / "migrations"
    directory.mkdir()
    for path in MIGRATIONS.iterdir():
        if path.name < "004":
            (directory / path.name).write_text(path.read_text())
    assert len(migrate(db, directory)) == 3
    (directory / "004_wheels_stacks.sql").write_text(
        (MIGRATIONS / "004_wheels_stacks.sql").read_text()
    )
    assert migrate(db, directory) == ["004_wheels_stacks.sql"]
    assert {"wheel", "stack", "stack_layer", "wheel_slot"} <= names(db, "table")
    assert {
        "stack_layer_shade",
        "wheel_slot_stack",
        "wheel_slot_draft",
    } <= names(db, "index")


def test_004_enforces_its_checks_and_cascades(tmp_path):
    db = str(tmp_path / "polished.db")
    migrate(db)
    conn = sqlite3.connect(db)
    conn.execute("pragma foreign_keys = on")
    conn.execute("insert into wheel (slug, name) values ('abc234', 'Holos')")
    assert conn.execute("select slot_count, archived from wheel").fetchone() == (20, 0)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into wheel (slug, name) values ('abc234', 'Same slug')")
    for count in (0, 41):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "insert into wheel (slug, name, slot_count) values (?, 'x', ?)",
                (f"s{count}", count),
            )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into stack (status) values ('published')")
    stack = conn.execute("insert into stack default values").lastrowid
    assert conn.execute("select status from stack").fetchone() == ("draft",)
    conn.execute(
        "insert into wheel_slot (wheel_id, position, draft_stack_id) values (1, 3, ?)", (stack,)
    )
    conn.execute("delete from stack where id = ?", (stack,))
    assert conn.execute("select draft_stack_id from wheel_slot").fetchone() == (None,)
    conn.execute("delete from wheel where id = 1")
    assert conn.execute("select count(*) from wheel_slot").fetchone() == (0,)
    conn.close()
