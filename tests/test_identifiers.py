import pytest
from conftest import make_settings
from shade_data import made_from, seed, shade_id

from polished import identifiers
from polished.db import connect
from polished.migrate import migrate

# resolve(), learn() and the learned codes (stage 5)

SPIRIT = made_from("thirst-trap", 1, "Spirit Fingers")
OTHER = made_from("thirst-trap", 2, "Other Shade")
SPIRIT_UPC = "810170284120"
SPIRIT_GTIN = "0810170284120"


@pytest.fixture
def db(tmp_path):
    settings = make_settings(tmp_path)
    migrate(settings.db_path)
    conn = connect(settings.db_path)
    seed(conn, [SPIRIT, OTHER])
    yield conn
    conn.close()


def sid(db, title):
    return db.execute("select id from shade where title = ?", (title,)).fetchone()["id"]


def test_an_unknown_barcode_is_unknown_code_with_the_13_digit_form(db):
    result = identifiers.resolve(db, SPIRIT_UPC, "scan")
    assert (result.outcome, result.code, result.via) == ("unknown_code", SPIRIT_GTIN, "scan")
    assert identifiers.resolve(db, SPIRIT_GTIN).outcome == "unknown_code"


def test_a_learned_gtin_is_a_match_and_counts_its_use(db):
    shade = sid(db, "Spirit Fingers")
    learned = identifiers.learn(db, "gtin", SPIRIT_UPC, shade)
    assert (learned.value, learned.created) == (SPIRIT_GTIN, True)
    for wanted_uses in (1, 2):
        result = identifiers.resolve(db, SPIRIT_GTIN, "scan")
        assert (result.outcome, result.kind, result.shade["id"]) == ("match", "gtin", shade)
        assert result.identifier_id == learned.id
        row = identifiers.get(db, learned.id)
        assert row["use_count"] == wanted_uses and row["last_used_at"]
    assert identifiers.resolve(db, SPIRIT_UPC).outcome == "match"  # either spelling finds it


def test_a_short_number_is_a_name_search_not_a_code(db):
    for typed in ("259", "p259", " P 259 "):
        result = identifiers.resolve(db, typed)
        assert (result.outcome, result.code, result.kind) == ("results", None, None)
        assert result.results is not None and result.results.rows == []


def test_a_number_that_fails_the_barcode_check_is_invalid_code(db):
    for typed in ("12345678901", "795203598", "810170284121", "123456789012345"[:14]):
        assert identifiers.resolve(db, typed).outcome == "invalid_code", typed
    # Too long or too short for a barcode: an ordinary search.
    assert identifiers.resolve(db, "123456").outcome == "results"
    assert identifiers.resolve(db, "1234567").outcome == "results"


def test_the_steps_run_in_order_gtin_then_number_then_sku_then_name(db):
    shade = sid(db, "Spirit Fingers")
    other = sid(db, "Other Shade")
    # A learned gtin beats a name search that would also find the shade.
    identifiers.learn(db, "gtin", SPIRIT_UPC, other)
    assert identifiers.resolve(db, SPIRIT_UPC).shade["id"] == other
    # The SKU is a catalog fact; it is only consulted after the code steps.
    sku = db.execute("select sku from shade where id = ?", (shade,)).fetchone()["sku"]
    result = identifiers.resolve(db, sku.lower())
    assert (result.outcome, result.kind, result.shade["id"]) == ("match", "sku", shade)
    assert result.identifier_id is None
    # Anything else is a name search.
    by_name = identifiers.resolve(db, "spirit")
    assert by_name.outcome == "results"
    assert [row["title"] for row in by_name.results.rows] == ["Spirit Fingers"]


def test_an_empty_query_has_no_results(db):
    result = identifiers.resolve(db, "   ")
    assert result.outcome == "results" and result.results is None


def test_a_conflicting_gtin_keeps_the_old_mapping(db):
    first, second = sid(db, "Spirit Fingers"), sid(db, "Other Shade")
    identifiers.learn(db, "gtin", SPIRIT_UPC, first)
    again = identifiers.learn(db, "gtin", SPIRIT_GTIN, second)
    assert (again.created, again.shade_id) == (False, first)
    assert identifiers.resolve(db, SPIRIT_UPC).shade["id"] == first
    assert db.execute("select count(*) from shade_identifier").fetchone()[0] == 1


def test_learning_a_value_that_is_not_a_code_raises(db):
    shade = sid(db, "Spirit Fingers")
    with pytest.raises(ValueError):
        identifiers.learn(db, "gtin", "795203598", shade)
    with pytest.raises(ValueError):
        identifiers.learn(db, "printed", "P259", shade)
    with pytest.raises(ValueError):
        identifiers.learn(db, "sku", "HL-1", shade)


def test_delete_forgets_the_mapping(db):
    shade = sid(db, "Spirit Fingers")
    learned = identifiers.learn(db, "gtin", SPIRIT_UPC, shade)
    identifiers.delete(db, learned.id)
    assert identifiers.resolve(db, SPIRIT_UPC).outcome == "unknown_code"
    assert identifiers.list_all(db) == []


def test_deleting_a_shade_deletes_its_mappings(db):
    other = sid(db, "Other Shade")
    identifiers.learn(db, "gtin", SPIRIT_UPC, other)
    db.execute("delete from shade where id = ?", (other,))
    assert identifiers.list_all(db) == []


def test_nothing_is_ever_seeded_from_catalog_data(tmp_path):
    """Catalog variants may carry a barcode (Spirit Fingers' reads 810065564276 there, and the real
    bottle reads something else). A sync, with that value in the feed, leaves shade_identifier
    empty and the value unknown."""
    settings = make_settings(tmp_path)
    migrate(settings.db_path)
    conn = connect(settings.db_path)
    with_barcode = made_from("thirst-trap", 3, "Catalog Barcode")
    with_barcode["variants"][0]["barcode"] = "810065564276"
    with_nine_digits = made_from("thirst-trap", 4, "Nine Digits")
    with_nine_digits["variants"][0]["barcode"] = "795203598"
    seed(conn, [with_barcode, with_nine_digits])
    assert conn.execute("select count(*) from shade where title = 'Catalog Barcode'").fetchone()[0]
    assert conn.execute("select count(*) from shade_identifier").fetchone()[0] == 0
    assert identifiers.resolve(conn, "810065564276").outcome == "unknown_code"
    assert identifiers.resolve(conn, "795203598").outcome == "invalid_code"
    assert conn.execute("select count(*) from shade_identifier").fetchone()[0] == 0
    assert shade_id(conn, "thirst-trap")  # the catalog itself is intact
    conn.close()


def test_the_catalog_barcode_of_spirit_fingers_does_not_identify_it(db):
    assert identifiers.resolve(db, "810065564276").outcome == "unknown_code"
