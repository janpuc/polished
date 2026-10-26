"""The wear log: what was painted on which day, and today's pick for "Wear today". Takes a
connection and a date; knows nothing about HTTP, so the web page and the API share it.

Days are the household's local dates, passed in as `today` (see `local_today`)."""

import random
import sqlite3
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import bottles

RECENT_DAYS = 30
# A shade worn today is still a candidate (a shelf of one), just a far less likely one.
LEAST_WEIGHT = 0.1


def local_today(timezone: str, now: datetime | None = None) -> date:
    """The date it is now in the household's time zone."""
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone)).date()


def record(conn: sqlite3.Connection, shade_id: int, today: date) -> str:
    """Logs the shade as worn on `today`; doing it again the same day changes nothing. Returns the
    date as YYYY-MM-DD. Raises LookupError for an unknown shade."""
    if conn.execute("select 1 from shade where id = ?", (shade_id,)).fetchone() is None:
        raise LookupError(shade_id)
    conn.execute(
        "insert into wear (shade_id, worn_on) values (?, ?) on conflict (shade_id, worn_on) do nothing",
        (shade_id, today.isoformat()),
    )
    return today.isoformat()


def worn_today(conn: sqlite3.Connection, shade_id: int, today: date) -> bool:
    row = conn.execute(
        "select 1 from wear where shade_id = ? and worn_on = ?", (shade_id, today.isoformat())
    ).fetchone()
    return row is not None


def candidates(conn: sqlite3.Connection) -> list[int]:
    """Shades that have a bottle which is neither archived nor empty, by id."""
    rows = conn.execute("select shade_id from shade_status where owned_count > 0 order by shade_id")
    return [r["shade_id"] for r in rows]


def _weights(
    conn: sqlite3.Connection, ids: list[int], today: date, through_today: bool
) -> list[float]:
    """1 for a shade not worn in the last RECENT_DAYS days, rising from LEAST_WEIGHT to 1 as the
    last wearing gets older. `through_today` counts wearings of today as well."""
    since = (today - timedelta(days=RECENT_DAYS)).isoformat()
    until = today.isoformat()
    last = {
        r["shade_id"]: date.fromisoformat(r["last"])
        for r in conn.execute(
            "select shade_id, max(worn_on) as last from wear"
            f" where worn_on > ? and worn_on {'<=' if through_today else '<'} ? group by shade_id",
            (since, until),
        )
    }
    weights = []
    for shade_id in ids:
        if shade_id not in last:
            weights.append(1.0)
        else:
            age = (today - last[shade_id]).days
            weights.append(LEAST_WEIGHT + (1 - LEAST_WEIGHT) * age / RECENT_DAYS)
    return weights


def pick_today(conn: sqlite3.Connection, today: date) -> int | None:
    """Today's shade: the same one all day (a generator seeded by the date over the wearings
    before today), unless something was already worn today, which is shown instead. None when
    nothing is owned."""
    ids = candidates(conn)
    if not ids:
        return None
    worn = conn.execute(
        "select w.shade_id from wear w join shade_status ss on ss.shade_id = w.shade_id"
        " where w.worn_on = ? and ss.owned_count > 0 order by w.id desc limit 1",
        (today.isoformat(),),
    ).fetchone()
    if worn is not None:
        return worn["shade_id"]
    rng = random.Random(f"wear:{today.isoformat()}")
    return rng.choices(ids, _weights(conn, ids, today, through_today=False))[0]


def pick_another(
    conn: sqlite3.Connection, today: date, not_this: int | None, rng: random.Random | None = None
) -> int | None:
    """A different owned shade than `not_this`, chosen at random but weighted away from the ones
    worn in the last RECENT_DAYS days. With only one shade owned that shade comes back; None when
    nothing is owned."""
    ids = candidates(conn)
    others = [i for i in ids if i != not_this] or ids
    if not others:
        return None
    weights = _weights(conn, others, today, through_today=True)
    return (rng or random).choices(others, weights)[0]


def bottle_for(conn: sqlite3.Connection, shade_id: int) -> dict | None:
    """The bottle to wear: the newest one that is neither archived nor empty."""
    return next((b for b in bottles.for_shade(conn, shade_id) if bottles.is_owned(b)), None)
