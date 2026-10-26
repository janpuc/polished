"""The wear log and today's pick (src/polished/wear.py)."""

import random
from datetime import UTC, date, datetime, timedelta

import pytest

from polished import bottles, shades, wear
from polished.bottles import BottleInput

TODAY = date(2026, 10, 26)
PINNED_PICK = 5  # the fifth of twelve ids, drawn from Random("wear:2026-10-26")


def add_shades(conn, count: int) -> list[int]:
    return [shades.create_manual(conn, f"Shade {n}", "polish") for n in range(count)]


def own(conn, shade_id: int, state: str = "full", archived: bool = False) -> int:
    bottle_id = bottles.add(conn, shade_id, BottleInput(state=state))
    if archived:
        bottles.set_archived(conn, bottle_id, True)
    return bottle_id


def wear_on(conn, shade_id: int, day: date) -> None:
    wear.record(conn, shade_id, day)


def test_local_today_is_the_households_date_not_utc():
    late = datetime(2026, 10, 25, 23, 30, tzinfo=UTC)  # already the 26th in Warsaw (CEST)
    assert wear.local_today("Europe/Warsaw", late) == date(2026, 10, 26)
    assert wear.local_today("UTC", late) == date(2026, 10, 25)
    assert wear.local_today("America/Los_Angeles", late) == date(2026, 10, 25)


def test_record_logs_the_day_once(conn):
    (shade,) = add_shades(conn, 1)
    assert wear.record(conn, shade, TODAY) == "2026-10-26"
    assert wear.record(conn, shade, TODAY) == "2026-10-26"  # a repeated tap changes nothing
    assert conn.execute("select count(*) from wear").fetchone()[0] == 1
    wear.record(conn, shade, TODAY + timedelta(days=1))
    assert conn.execute("select count(*) from wear").fetchone()[0] == 2


def test_record_refuses_an_unknown_shade(conn):
    with pytest.raises(LookupError):
        wear.record(conn, 999, TODAY)
    assert conn.execute("select count(*) from wear").fetchone()[0] == 0


def test_worn_today_is_per_shade_and_per_day(conn):
    first, second = add_shades(conn, 2)
    assert not wear.worn_today(conn, first, TODAY)
    wear.record(conn, first, TODAY)
    assert wear.worn_today(conn, first, TODAY)
    assert not wear.worn_today(conn, second, TODAY)
    assert not wear.worn_today(conn, first, TODAY + timedelta(days=1))


def test_only_shades_with_a_bottle_that_is_neither_archived_nor_empty_are_candidates(conn):
    kept, empty, archived, none, mixed = add_shades(conn, 5)
    own(conn, kept, "low")
    own(conn, empty, "empty")
    own(conn, archived, "full", archived=True)
    own(conn, mixed, "empty")
    own(conn, mixed, "half")
    assert wear.candidates(conn) == [kept, mixed]
    assert none not in wear.candidates(conn)


def test_nothing_owned_means_no_pick(conn):
    add_shades(conn, 3)
    assert wear.pick_today(conn, TODAY) is None
    assert wear.pick_another(conn, TODAY, not_this=None) is None


def test_the_pick_is_the_same_all_day_and_across_processes_seeded_by_the_date(conn):
    for shade in add_shades(conn, 12):
        own(conn, shade)
    first = wear.pick_today(conn, TODAY)
    assert {wear.pick_today(conn, TODAY) for _ in range(20)} == {first}
    # Another day is another draw; over a month the picks are not all one shade.
    picks = {wear.pick_today(conn, TODAY + timedelta(days=n)) for n in range(30)}
    assert len(picks) > 3


def test_the_pick_does_not_depend_on_the_process(conn):
    """random.Random(str) hashes with sha512, not hash(), so PYTHONHASHSEED cannot move it."""
    for shade in add_shades(conn, 12):
        own(conn, shade)
    assert wear.pick_today(conn, TODAY) == PINNED_PICK


def test_wearing_the_pick_does_not_change_the_pick(conn):
    for shade in add_shades(conn, 12):
        own(conn, shade)
    pick = wear.pick_today(conn, TODAY)
    wear.record(conn, pick, TODAY)
    assert wear.pick_today(conn, TODAY) == pick


def test_what_was_worn_today_is_shown_instead_of_the_draw(conn):
    shades_ = add_shades(conn, 12)
    for shade in shades_:
        own(conn, shade)
    pick = wear.pick_today(conn, TODAY)
    other = next(s for s in shades_ if s != pick)
    wear.record(conn, other, TODAY)
    assert wear.pick_today(conn, TODAY) == other
    # ... unless it is no longer owned: then the draw is made again.
    conn.execute("update bottle set state = 'empty' where shade_id = ?", (other,))
    assert wear.pick_today(conn, TODAY) in wear.candidates(conn)


def test_recent_wearings_weigh_the_pick_away(conn):
    recent, fresh = add_shades(conn, 2)
    own(conn, recent)
    own(conn, fresh)
    wear.record(conn, recent, TODAY - timedelta(days=1))
    weights = wear._weights(conn, [recent, fresh], TODAY, through_today=False)
    assert weights[1] == 1.0
    assert wear.LEAST_WEIGHT < weights[0] < 0.2
    # The draw over the other days is seeded by the date alone, so it does not drift between runs.
    assert wear.pick_today(conn, TODAY) in (recent, fresh)


def test_the_weight_returns_to_one_after_thirty_days(conn):
    (shade,) = add_shades(conn, 1)
    own(conn, shade)
    wear.record(conn, shade, TODAY - timedelta(days=29))
    assert wear._weights(conn, [shade], TODAY, False)[0] == pytest.approx(
        wear.LEAST_WEIGHT + (1 - wear.LEAST_WEIGHT) * 29 / 30
    )
    wear.record(conn, shade, TODAY - timedelta(days=30))
    conn.execute("delete from wear where worn_on = ?", ((TODAY - timedelta(days=29)).isoformat(),))
    assert wear._weights(conn, [shade], TODAY, False) == [1.0]


def test_pick_another_never_returns_the_shade_it_was_told_to_avoid(conn):
    ids = add_shades(conn, 5)
    for shade in ids:
        own(conn, shade)
    rng = random.Random(1)
    for avoid in ids:
        for _ in range(30):
            assert wear.pick_another(conn, TODAY, avoid, rng) != avoid


def test_pick_another_with_one_shade_owned_returns_it(conn):
    (shade,) = add_shades(conn, 1)
    own(conn, shade)
    assert wear.pick_another(conn, TODAY, shade) == shade


def test_pick_another_is_weighted_away_from_the_last_30_days(conn):
    worn, fresh, avoided = add_shades(conn, 3)
    for shade in (worn, fresh, avoided):
        own(conn, shade)
    for days_ago in range(0, 10):  # worn nearly every day lately
        wear.record(conn, worn, TODAY - timedelta(days=days_ago))
    rng = random.Random(7)
    counts = {worn: 0, fresh: 0}
    for _ in range(600):
        counts[wear.pick_another(conn, TODAY, avoided, rng)] += 1
    assert counts[fresh] > 4 * counts[worn]
    assert counts[worn] > 0  # weighted away, not excluded


def test_bottle_for_is_the_newest_that_can_be_worn(conn):
    (shade,) = add_shades(conn, 1)
    old = own(conn, shade, "half")
    gone = own(conn, shade, "empty")
    new = own(conn, shade, "low")
    hidden = own(conn, shade, "full", archived=True)
    assert wear.bottle_for(conn, shade)["id"] == new
    bottles.set_state(conn, new, "empty")
    assert wear.bottle_for(conn, shade)["id"] == old
    assert gone != hidden  # an empty and an archived bottle are never worn
    assert wear.bottle_for(conn, add_shades(conn, 1)[0]) is None
