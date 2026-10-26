import logging

import pytest
from conftest import FIXTURES

from polished.catalog import sheet as sheet_module
from polished.catalog.sheet import (
    SheetError,
    SheetRow,
    is_topper_name,
    normalise_name,
    parse_date,
    parse_sheet,
)

HEADER = "Release date,Shade name,Simply Swatch,In Collection,Retired?,I got it!,Wishlist ,,"


def fixture_text() -> str:
    return (FIXTURES / "release_sheet_trimmed.csv").read_text(encoding="utf-8")


def table(*rows: str, header: str = HEADER, preamble: str = ",,,,,,,,") -> str:
    return "\r\n".join([preamble, header, *rows]) + "\r\n"


def by_name(rows: list[SheetRow], name: str) -> SheetRow:
    return next(r for r in rows if r.name == name)


# Names


@pytest.mark.parametrize(
    ("shop", "sheet"),
    [
        ("Flakie Holo Taco™", "Flakie Holo Taco"),
        ("Aurora Unicorn Skin™", "aurora unicorn skin"),
        ("Matte Taco®", "Matte Taco"),
        ("Play Rosé", "Play Rose"),
        ("Royal-Tea Blue", "Royal Tea Blue"),
        ("Don’t Stop", "Dont Stop"),
        ("Rock & Roll", "Rock and Roll"),
        ("  Got   Cake? ", "Got Cake"),
    ],
)
def test_names_match_after_normalising(shop, sheet):
    assert normalise_name(shop) == normalise_name(sheet) != ""


def test_different_names_stay_different():
    assert normalise_name("Blue Flakie Holo Taco") != normalise_name("Blue Flake Taco")


@pytest.mark.parametrize(
    ("name", "topper"),
    [
        ("Silver Flake Taco", True),
        ("Gold Scattered Holo Taco", True),
        ("Cracked Taco Shell", True),
        ("Purple Flakie Holo Taco", True),
        ("Silent Night", False),
        ("Call Me Vixen", False),
        ("Pirouette Pink", False),
    ],
)
def test_a_sheet_only_shade_is_a_topper_when_its_name_says_taco_or_flake(name, topper):
    assert is_topper_name(normalise_name(name)) is topper


# Dates


@pytest.mark.parametrize(
    ("text", "iso"),
    [
        ("Jul 6, 2019", "2019-07-06"),
        ("Dec 31, 2025", "2025-12-31"),
        ("Sept 3, 2024", "2024-09-03"),
        ("Oct. 16, 2026", "2026-10-16"),
        ("2019-07-06", "2019-07-06"),
        ("  Nov 15, 2025 ", "2025-11-15"),
    ],
)
def test_dates_become_iso(text, iso):
    assert parse_date(text) == iso


@pytest.mark.parametrize(
    "text", ["", "TBA", "Feb 30, 2024", "Foo 3, 2024", "2024-13-01", "6 Jul 2019"]
)
def test_unreadable_dates_are_none(text):
    assert parse_date(text) is None


# The table


def test_the_fixture_parses_with_its_preamble_and_quoted_cells():
    rows = parse_sheet(fixture_text(), min_rows=1)
    assert len(rows) == 13
    first = rows[0]
    assert first == SheetRow(
        key="royal tea blue",
        name="Royal-Tea Blue",
        released_on="2019-07-06",
        collection="Holo Taco Launch Collection",
        retired=False,
    )
    assert by_name(rows, "Rest In Peach").collection == "Pastel & Don't Tell Bundle"
    assert by_name(rows, "Play Rosé").key == "play rose"


def test_only_the_word_retired_means_retired():
    rows = parse_sheet(fixture_text(), min_rows=1)
    assert by_name(rows, "Red Flake Taco").retired
    assert by_name(rows, "Hit The Lights").retired
    assert not by_name(rows, "Glow In The Dark Taco").retired  # "Seasonal"
    assert not by_name(rows, "Silver Flake Taco").retired


def test_the_columns_are_found_by_name_not_by_position():
    text = "\r\n".join(
        [
            ",,,",
            "I got it!,Retired?,Shade name,Release date,In Collection",
            'FALSE,Retired,One-Coat Black,"Jul 6, 2019",Holo Taco Launch Collection',
        ]
    )
    (row,) = parse_sheet(text, min_rows=1)
    assert (row.name, row.released_on, row.collection, row.retired) == (
        "One-Coat Black",
        "2019-07-06",
        "Holo Taco Launch Collection",
        True,
    )


def test_blank_rows_notes_and_rows_without_a_date_are_skipped(caplog):
    text = table(
        '"Jul 6, 2019",One-Coat Black,,Holo Taco Launch Collection,,FALSE,FALSE,,',
        ",,,,,,,,",
        "",
        "TBA,Mystery Shade,,Next Collection,,FALSE,FALSE,,",
        ',"Note: more shades are coming",,,,,,,',
        '"Jul 6, 2019",,,Holo Taco Launch Collection,,FALSE,FALSE,,',
    )
    with caplog.at_level(logging.WARNING, logger="polished.sync"):
        rows = parse_sheet(text, min_rows=1)
    assert [r.name for r in rows] == ["One-Coat Black"]
    assert "2 row(s) without a readable date" in caplog.text


def test_short_rows_and_a_missing_collection_are_fine():
    (row,) = parse_sheet(table('"Jul 6, 2019",One-Coat Black'), min_rows=1)
    assert (row.collection, row.retired) == (None, False)


def test_a_name_listed_twice_keeps_the_earliest_date(caplog):
    text = table(
        '"Jul 6, 2021",Royal-Tea Blue,,Rerelease,,FALSE,FALSE,,',
        '"Jul 6, 2019",Royal Tea Blue,,Holo Taco Launch Collection,,FALSE,FALSE,,',
    )
    with caplog.at_level(logging.WARNING, logger="polished.sync"):
        (row,) = parse_sheet(text, min_rows=1)
    assert (row.released_on, row.collection) == ("2019-07-06", "Holo Taco Launch Collection")
    assert "twice" in caplog.text


def test_lf_line_endings_are_fine():
    text = fixture_text().replace("\r\n", "\n")
    assert len(parse_sheet(text, min_rows=1)) == 13


# A layout that changed is an error, never a partial read


def test_no_header_row_is_an_error():
    with pytest.raises(SheetError, match="header row"):
        parse_sheet("<!doctype html><html><body>Sign in</body></html>", min_rows=1)
    with pytest.raises(SheetError, match="header row"):
        parse_sheet(table("a,b", header="Date,Name"), min_rows=1)


def test_a_header_row_missing_a_column_is_an_error():
    with pytest.raises(SheetError, match="in collection"):
        parse_sheet(table(header="Release date,Shade name,Retired?"), min_rows=1)
    with pytest.raises(SheetError, match="retired"):
        parse_sheet(table(header="Release date,Shade name,In Collection"), min_rows=1)


def test_fewer_than_300_shades_is_an_error():
    rows = [f'"Jul 6, 2019",Shade {n},,Collection,,FALSE,FALSE,,' for n in range(299)]
    with pytest.raises(SheetError, match="only 299 shades"):
        parse_sheet(table(*rows))
    assert (
        len(parse_sheet(table(*rows, '"Jul 6, 2019",Shade 299,,Collection,,FALSE,FALSE,,'))) == 300
    )


def test_the_minimum_is_the_module_constant(monkeypatch):
    monkeypatch.setattr(sheet_module, "MIN_ROWS", 2)
    with pytest.raises(SheetError):
        parse_sheet(table('"Jul 6, 2019",One,,C,,FALSE,FALSE,,'))
    assert len(parse_sheet(table('"Jul 6, 2019",One', '"Jul 7, 2019",Two'))) == 2
