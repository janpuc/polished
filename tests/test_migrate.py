import sqlite3

import pytest
from conftest import migrations_below

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
        "007_release_sheet.sql",
        "008_api_tokens.sql",
        "009_wear.sql",
        "010_wipe_printed_codes.sql",
        "011_matte_taco_finish.sql",
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
        (7, "007_release_sheet.sql"),
        (8, "008_api_tokens.sql"),
        (9, "009_wear.sql"),
        (10, "010_wipe_printed_codes.sql"),
        (11, "011_matte_taco_finish.sql"),
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
        "007_release_sheet.sql",
        "008_api_tokens.sql",
        "009_wear.sql",
        "010_wipe_printed_codes.sql",
        "011_matte_taco_finish.sql",
    ]


def test_002_inventory_applies_on_top_of_a_synced_001_database(tmp_path):
    from polished.db import connect

    db = str(tmp_path / "polished.db")
    only_001 = tmp_path / "only_001"
    only_001.mkdir()
    for name in ("001_catalog.sql", "005_swatch_image.sql"):
        (only_001 / name).write_text((MIGRATIONS / name).read_text())
    assert migrate(db, only_001) == ["001_catalog.sql", "005_swatch_image.sql"]
    conn = connect(db)
    for number in range(9):
        conn.execute(
            "insert into shade (kind, title, search_text) values ('polish', ?, ?)",
            (f"Shade {number}", f"shade {number}"),
        )
    shades = conn.execute("select count(*) from shade").fetchone()[0]
    assert shades == 9
    assert "bottle" not in names(db, "table")

    assert migrate(db) == [
        "002_inventory.sql",
        "003_identifiers.sql",
        "004_wheels_stacks.sql",
        "006_swatch_colour.sql",
        "007_release_sheet.sql",
        "008_api_tokens.sql",
        "009_wear.sql",
        "010_wipe_printed_codes.sql",
        "011_matte_taco_finish.sql",
    ]
    assert names(db, "table") >= {"bottle", "wishlist_item"}
    assert names(db, "index") >= {"bottle_shade"}
    assert "bottle_printed_code" not in names(db, "index")
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


def populated_006_database(tmp_path):
    """A database at migration 006 holding what a deployed one holds: a synced product with tags,
    a bottle, a wish, a stack layer, a learned code and an alias, all pointing at shades."""
    from polished.db import connect

    db = str(tmp_path / "polished.db")
    directory = tmp_path / "up_to_006"
    directory.mkdir()
    for path in MIGRATIONS.iterdir():
        if path.name < "007":
            (directory / path.name).write_text(path.read_text())
    assert len(migrate(db, directory)) == 6
    conn = connect(db)
    for number in (1, 2):
        conn.execute(
            "insert into product (id, shopify_product_id, variant_id, handle, title, product_type,"
            " role, available, tags_json, raw_json, content_hash, last_seen)"
            " values (?, ?, ?, ?, ?, 'Nail Polish', 'shade', 1, '[]', '{}', 'x', 'now')",
            (number, 100 + number, 200 + number, f"shade-{number}", f"Shade {number}"),
        )
        conn.execute(
            "insert into shade (id, product_id, kind, title, handle, sku, search_text,"
            " hero_image_url, price_cents, available, retired, swatch_image_url, swatch_hex,"
            " swatch_hex2, swatch_hex_src, swatch_override_hex)"
            " values (?, ?, 'polish', ?, ?, 'HL-1', ?, 'https://cdn.example.test/a.jpg', 1550, 1,"
            " ?, 'https://cdn.example.test/b.jpg', '#112233', '#445566', 'src', ?)",
            (
                number,
                number,
                f"Shade {number}",
                f"shade-{number}",
                f"shade {number}",
                number - 1,
                "#abcdef" if number == 1 else None,
            ),
        )
    conn.execute(
        "insert into shade (id, source, kind, title, search_text) values (3, 'manual', 'polish', 'Gift', 'gift')"
    )
    conn.execute("insert into shade_tag (shade_id, ns, value) values (1, 'finish', 'holographic')")
    conn.execute("insert into shade_tag (shade_id, ns, value) values (2, 'collection', 'vault')")
    conn.execute("insert into bottle (shade_id, printed_code, state) values (1, 'P1', 'half')")
    conn.execute("insert into bottle (shade_id, archived) values (3, 1)")
    conn.execute("insert into wishlist_item (shade_id, priority, note) values (2, 1, 'soon')")
    conn.execute(
        "insert into shade_identifier (kind, value, shade_id) values ('gtin', '0810170284120', 2)"
    )
    conn.execute(
        "insert into shade_identifier (kind, value, shade_id) values ('printed', 'P259', 1)"
    )
    conn.execute(
        "insert into product (id, shopify_product_id, variant_id, handle, title, product_type,"
        " role, available, tags_json, raw_json, content_hash, last_seen)"
        " values (9, 109, 209, 'gift', 'Gift', 'Birthday Gift', 'alias', 1, '[]', '{}', 'x', 'now')"
    )
    conn.execute("insert into shade_alias (product_id, shade_id, source) values (9, 1, 'handle')")
    stack = conn.execute("insert into stack default values").lastrowid
    conn.execute(
        "insert into stack_layer (stack_id, ord, shade_id, coats) values (?, 1, 1, 2)", (stack,)
    )
    return db, conn


def dump_tables(conn):
    return {
        table: [tuple(r) for r in conn.execute(f"select * from {table} order by 1, 2")]
        for table in (
            "product",
            "shade_tag",
            "bottle",
            "wishlist_item",
            "shade_identifier",
            "shade_alias",
            "stack_layer",
            "stack",
        )
    }


def test_007_rebuilds_shade_and_leaves_everything_that_points_at_it_alone(tmp_path):
    db, conn = populated_006_database(tmp_path)
    old_columns = [r["name"] for r in conn.execute("pragma table_info(shade)")]
    before_shades = [tuple(r) for r in conn.execute("select * from shade order by id")]
    before = dump_tables(conn)
    before_status = [tuple(r) for r in conn.execute("select * from shade_status order by 1")]

    assert migrate(db, migrations_below(tmp_path, 10)) == [
        "007_release_sheet.sql",
        "008_api_tokens.sql",
        "009_wear.sql",
    ]

    assert conn.execute("pragma foreign_key_check").fetchall() == []
    assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert dump_tables(conn) == before
    assert [
        tuple(r) for r in conn.execute("select * from shade_status order by 1")
    ] == before_status
    new_columns = [r["name"] for r in conn.execute("pragma table_info(shade)")]
    assert new_columns == old_columns + [
        "released_on",
        "official_collection",
        "sheet_retired",
        "sheet_key",
    ]
    after = [tuple(r) for r in conn.execute("select * from shade order by id")]
    assert [row[: len(old_columns)] for row in after] == before_shades
    assert {row[len(old_columns) :] for row in after} == {(None, None, 0, None)}
    # The tables that point at shade still point at "shade", not at a leftover name.
    for table in (
        "bottle",
        "wishlist_item",
        "shade_identifier",
        "shade_alias",
        "shade_tag",
        "stack_layer",
    ):
        assert [
            fk["table"]
            for fk in conn.execute(f"pragma foreign_key_list({table})")
            if fk["from"] == "shade_id"
        ] == ["shade"]
    assert names(db, "table") >= {"shade", "bottle"}
    assert not {"shade_new", "shade_old"} & names(db, "table")
    assert {"shade_kind", "shade_sku", "shade_handle", "shade_sheet_key"} <= names(db, "index")
    assert "shade_status" in names(db, "view")
    conn.close()


def test_007_keeps_the_cascades_and_the_checks_working(tmp_path):
    db, conn = populated_006_database(tmp_path)
    migrate(db, migrations_below(tmp_path, 10))
    # source accepts the new word and still refuses others
    conn.execute(
        "insert into shade (source, kind, title, search_text) values ('sheet', 'polish', 'S', 's')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into shade (source, kind, title, search_text) values ('web', 'polish', 'W', 'w')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("update shade set sheet_retired = 2 where id = 1")
    # one product still has one shade
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into shade (product_id, kind, title, search_text) values (1, 'polish', 'Dup', 'dup')"
        )
    # a sheet-only shade has a unique sheet key; other sources may share one
    conn.execute("update shade set sheet_key = 'k' where title = 'S'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into shade (source, kind, title, search_text, sheet_key) values ('sheet', 'polish', 'T', 't', 'k')"
        )
    conn.execute("update shade set sheet_key = 'k' where id = 1")
    # the cascades that existed still fire (foreign keys are on in this connection)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("delete from shade where id = 2")  # still wished for
    conn.execute("delete from wishlist_item")
    conn.execute("delete from shade where id = 2")
    assert conn.execute("select count(*) from shade_tag where shade_id = 2").fetchone()[0] == 0
    assert (
        conn.execute("select count(*) from shade_identifier where shade_id = 2").fetchone()[0] == 0
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("delete from shade where id = 1")  # still has a bottle
    assert conn.execute("select max(id) from shade").fetchone()[0] == 4
    conn.close()


def test_007_runs_against_a_foreign_keys_on_environment_without_cascading(tmp_path, monkeypatch):
    """migrate() turns foreign keys off itself, so a SQLite built with them on by default would
    not delete the tag, identifier and alias rows when the old table is dropped."""
    db, conn = populated_006_database(tmp_path)
    before = dump_tables(conn)
    real_connect = sqlite3.connect

    def connect_with_keys_on(*args, **kwargs):
        c = real_connect(*args, **kwargs)
        c.execute("pragma foreign_keys = on")
        return c

    monkeypatch.setattr("polished.migrate.sqlite3.connect", connect_with_keys_on)
    migrate(db, migrations_below(tmp_path, 10))
    assert dump_tables(conn) == before
    conn.close()


def test_a_migration_that_breaks_a_foreign_key_is_rolled_back(tmp_path):
    db = str(tmp_path / "polished.db")
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "001_parent.sql").write_text(
        "create table parent (id integer primary key);"
        "create table child (parent_id integer references parent (id));"
        "insert into parent (id) values (1);"
        "insert into child (parent_id) values (1);"
    )
    assert migrate(db, directory) == ["001_parent.sql"]
    (directory / "002_drop.sql").write_text("delete from parent;")
    with pytest.raises(sqlite3.IntegrityError, match="002_drop.sql broke a foreign key"):
        migrate(db, directory)
    conn = sqlite3.connect(db)
    assert conn.execute("select count(*) from parent").fetchone() == (1,)
    assert conn.execute("select max(version) from schema_version").fetchone() == (1,)
    conn.close()


def test_010_wipes_the_printed_codes_and_leaves_the_rest_of_a_populated_database_alone(tmp_path):
    db, conn = populated_006_database(tmp_path)
    migrate(db, migrations_below(tmp_path, 10))
    counts = {
        table: conn.execute(f"select count(*) from {table}").fetchone()[0]
        for table in ("shade", "bottle", "wishlist_item", "stack", "stack_layer", "shade_tag")
    }
    assert conn.execute("select printed_code from bottle where shade_id = 1").fetchone()[0] == "P1"
    assert conn.execute("select count(*) from shade_identifier").fetchone()[0] == 2
    bottles = [
        tuple(r)
        for r in conn.execute("select id, shade_id, state, archived, notes from bottle order by id")
    ]

    below_11 = migrations_below(tmp_path, 11)
    assert migrate(db, below_11) == ["010_wipe_printed_codes.sql"]
    assert migrate(db, below_11) == []  # idempotent

    assert [tuple(r) for r in conn.execute("select kind, value from shade_identifier")] == [
        ("gtin", "0810170284120")
    ]
    columns = [r["name"] for r in conn.execute("pragma table_info(bottle)")]
    assert "printed_code" not in columns
    assert "bottle_printed_code" not in names(db, "index")
    assert {"bottle_shade"} <= names(db, "index")
    for table, count in counts.items():
        assert conn.execute(f"select count(*) from {table}").fetchone()[0] == count, table
    assert [
        tuple(r)
        for r in conn.execute("select id, shade_id, state, archived, notes from bottle order by id")
    ] == bottles
    assert "shade_status" in names(db, "view")
    status = conn.execute("select * from shade_status where shade_id = 1").fetchone()
    assert (status["owned_count"], status["bottle_count"]) == (1, 1)
    assert conn.execute("pragma foreign_key_check").fetchall() == []
    assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    conn.close()


def test_011_gives_matte_taco_its_finish_and_kind_and_leaves_the_rest_alone(tmp_path):
    db = str(tmp_path / "live.db")
    assert migrate(db, migrations_below(tmp_path, 11))[-1] == "010_wipe_printed_codes.sql"
    conn = sqlite3.connect(db)
    for shade_id, handle, title in (
        (1, "matte-taco", "Matte Taco"),
        (2, "glossy-taco", "Glossy Taco"),
    ):
        conn.execute(
            "insert into shade (id, kind, title, handle, search_text, is_topper)"
            " values (?, ?, ?, ?, ?, 1)",
            (shade_id, "polish" if shade_id == 1 else "topcoat", title, handle, title.lower()),
        )
        conn.execute("insert into shade_tag values (?, 'color', 'clear')", (shade_id,))
    conn.execute("insert into bottle (shade_id) values (1)")
    conn.commit()
    conn.close()

    assert migrate(db) == ["011_matte_taco_finish.sql"]
    assert migrate(db) == []

    conn = sqlite3.connect(db)
    assert conn.execute(
        "select kind, is_topper, search_text from shade where id = 1"
    ).fetchone() == (
        "topcoat",
        1,
        "matte taco matte",
    )

    def tags(shade_id):
        return sorted(
            conn.execute("select ns, value from shade_tag where shade_id = ?", (shade_id,))
        )

    assert tags(1) == [("color", "clear"), ("finish", "matte")]
    assert tags(2) == [("color", "clear")]  # Glossy Taco needs nothing: gloss is the default
    assert conn.execute("select kind, search_text from shade where id = 2").fetchone() == (
        "topcoat",
        "glossy taco",
    )
    assert conn.execute("select count(*) from bottle").fetchone() == (1,)
    assert conn.execute("pragma foreign_key_check").fetchall() == []
    conn.close()
