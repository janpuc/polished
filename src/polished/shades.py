"""Finding shades: search, filters, sorting, pagination, status and the detail record
(DESIGN 5.3 and 6). Takes a connection; routes never write SQL."""

import json
import re
import sqlite3
from dataclasses import dataclass, field

from .catalog.parse import fold

PAGE_SIZE = 40
SEARCH_LIMIT = 30

KINDS = ("polish", "topper", "base")
STATUSES = ("buyable", "retired", "sold_out")
SORTS = ("name", "newest", "price")

# shade s left join product p. Same conditions as status() below, so a filter and a row's
# status never disagree (tests/test_shades.py checks it on every shade).
_LISTED = "p.missing_since is null"
STATUS_SQL = {
    "buyable": f"{_LISTED} and s.available = 1",
    "retired": f"{_LISTED} and s.retired = 1",
    "sold_out": f"{_LISTED} and s.retired = 0 and s.available = 0",
}
KIND_SQL = {
    "polish": "s.kind = 'polish' and s.is_topper = 0",
    "topper": "s.is_topper = 1",
    "base": "s.kind = 'basecoat'",
}
ORDER_SQL = {
    "name": "s.title collate nocase, s.id",
    "newest": "datetime(s.published_at) is null, datetime(s.published_at) desc,"
    " s.title collate nocase, s.id",
    "price": "s.price_cents is null, s.price_cents, s.title collate nocase, s.id",
}
_NOT_WORD = re.compile(r"[\W_]+")

FROM = "from shade s left join product p on p.id = s.product_id"


@dataclass(frozen=True)
class Status:
    key: str  # missing | retired | sold_out | retiring | available
    label: str
    buyable: bool


def status(shade) -> Status | None:
    """The state of a shade, first match wins (DESIGN 5.3). `shade` needs source, missing_since,
    retired, retiring and available (a row of the list or detail query). Manual shades have no
    status: nothing is known about a shop listing."""
    if shade["source"] == "manual":
        return None
    if shade["missing_since"]:
        return Status("missing", "Not listed", False)
    available = bool(shade["available"])
    if shade["retired"]:
        return Status("retired", "Retired, last stock" if available else "Retired", available)
    if not available:
        return Status("sold_out", "Sold out, retiring" if shade["retiring"] else "Sold out", False)
    if shade["retiring"]:
        return Status("retiring", "Retiring soon", True)
    return Status("available", "In stock", True)


def on_sale(shade) -> bool:
    return (
        shade["price_cents"] is not None
        and shade["compare_at_cents"] is not None
        and shade["price_cents"] < shade["compare_at_cents"]
    )


def tokens(text: str) -> list[str]:
    """Folded words of a query; the same folding the stored search_text went through."""
    return [t for t in _NOT_WORD.split(fold(text)) if t]


def _pick(value: str | None, allowed: tuple[str, ...], default: str = "") -> str:
    return value if value in allowed else default


@dataclass(frozen=True)
class ShadeQuery:
    """What the browse page and the home search ask for. Unknown values mean "no filter", so a
    stale bookmark still shows a list."""

    q: str = ""
    finish: tuple[str, ...] = ()
    color: tuple[str, ...] = ()
    collection: str = ""
    kind: str = ""
    status: str = ""
    sort: str = "name"

    @classmethod
    def from_params(
        cls,
        q: str | None = None,
        finish: list[str] | None = None,
        color: list[str] | None = None,
        collection: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        sort: str | None = None,
    ) -> "ShadeQuery":
        return cls(
            q=(q or "").strip()[:100],
            finish=tuple(dict.fromkeys(v for v in finish or [] if v)),
            color=tuple(dict.fromkeys(v for v in color or [] if v)),
            collection=(collection or "").strip(),
            kind=_pick(kind, KINDS),
            status=_pick(status, STATUSES),
            sort=_pick(sort, SORTS, "name"),
        )

    def filter_count(self) -> int:
        """How many filters are on (the Filters button shows it); search and sort are not."""
        return (
            len(self.finish)
            + len(self.color)
            + bool(self.collection)
            + bool(self.kind)
            + bool(self.status)
        )

    def params(self, page: int = 1) -> list[tuple[str, str]]:
        """Only what differs from the defaults, for a Load more URL."""
        pairs = [("q", self.q)] if self.q else []
        pairs += [("finish", v) for v in self.finish] + [("color", v) for v in self.color]
        for name in ("collection", "kind", "status"):
            if getattr(self, name):
                pairs.append((name, getattr(self, name)))
        if self.sort != "name":
            pairs.append(("sort", self.sort))
        if page > 1:
            pairs.append(("page", str(page)))
        return pairs


@dataclass
class ShadePage:
    rows: list[dict] = field(default_factory=list)
    total: int = 0
    page: int = 1
    has_more: bool = False


def _tag_clause(ns: str, values: tuple[str, ...], where: list[str], args: list) -> None:
    marks = ", ".join("?" * len(values))
    where.append(
        "exists (select 1 from shade_tag t where t.shade_id = s.id"
        f" and t.ns = '{ns}' and t.value in ({marks}))"
    )
    args.extend(values)


def _where(query: ShadeQuery) -> tuple[str, list]:
    where: list[str] = []
    args: list = []
    for token in tokens(query.q):
        where.append("s.search_text like ?")
        args.append(f"%{token}%")
    if query.finish:
        _tag_clause("finish", query.finish, where, args)
    if query.color:
        _tag_clause("color", query.color, where, args)
    if query.collection:
        _tag_clause("collection", (query.collection,), where, args)
    if query.kind:
        where.append(KIND_SQL[query.kind])
    if query.status:
        where.append(STATUS_SQL[query.status])
    return (" where " + " and ".join(where)) if where else "", args


def _order(query: ShadeQuery) -> tuple[str, list]:
    """A search by name puts titles that start with the query first (search_text starts with the
    folded title), then alphabetical."""
    words = tokens(query.q)
    if words and query.sort == "name":
        return (
            "(s.search_text like ?) desc, " + ORDER_SQL["name"],
            [" ".join(words) + "%"],
        )
    return ORDER_SQL[query.sort], []


def _with_finishes(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict]:
    finishes: dict[int, list[str]] = {}
    if rows:
        marks = ", ".join("?" * len(rows))
        for tag in conn.execute(
            f"select shade_id, value from shade_tag where ns = 'finish'"
            f" and shade_id in ({marks}) order by value",
            [r["id"] for r in rows],
        ):
            finishes.setdefault(tag["shade_id"], []).append(tag["value"])
    return [
        {**row, "status": status(row), "finishes": finishes.get(row["id"], [])}
        for row in map(dict, rows)
    ]


def list_shades(
    conn: sqlite3.Connection, query: ShadeQuery, page: int = 1, size: int = PAGE_SIZE
) -> ShadePage:
    """One page of shades: rows with a Status and their finish values, and the total."""
    page = max(page, 1)
    where, args = _where(query)
    order, order_args = _order(query)
    total = conn.execute(f"select count(*) {FROM}{where}", args).fetchone()[0]
    rows = conn.execute(
        "select s.id, s.title, s.kind, s.source, s.hero_image_url, s.price_cents,"
        " s.compare_at_cents, s.available, s.retired, s.retiring, s.is_topper,"
        f" p.missing_since {FROM}{where} order by {order} limit ? offset ?",
        [*args, *order_args, size, (page - 1) * size],
    ).fetchall()
    return ShadePage(
        rows=_with_finishes(conn, rows),
        total=total,
        page=page,
        has_more=page * size < total,
    )


def search(conn: sqlite3.Connection, text: str, limit: int = SEARCH_LIMIT) -> ShadePage:
    """The home typeahead: the first `limit` matches of a name search."""
    return list_shades(conn, ShadeQuery.from_params(q=text), size=limit)


def facets(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """The tag values to offer as filters: finishes and colours most common first,
    collections alphabetical."""
    result: dict[str, list[str]] = {}
    for ns, order in (
        ("finish", "count(*) desc, value"),
        ("color", "count(*) desc, value"),
        ("collection", "value"),
    ):
        result[ns] = [
            r["value"]
            for r in conn.execute(
                f"select value from shade_tag where ns = ? group by value order by {order}", (ns,)
            )
        ]
    return result


def get_shade(conn: sqlite3.Connection, shade_id: int) -> dict | None:
    """Everything the detail page shows: the shade, its status, tags by namespace, all product
    images (from the product's raw feed JSON), and the product handle for the shop link."""
    row = conn.execute(
        f"select s.*, p.missing_since, p.raw_json {FROM} where s.id = ?", (shade_id,)
    ).fetchone()
    if row is None:
        return None
    shade = dict(row)
    images: list[str] = []
    raw_json = shade.pop("raw_json")
    if raw_json:
        feed_images = json.loads(raw_json).get("images", [])
        images = [i["src"] for i in sorted(feed_images, key=lambda i: i.get("position", 0))]
    if not images and shade["hero_image_url"]:
        images = [shade["hero_image_url"]]
    tags: dict[str, list[str]] = {"finish": [], "color": [], "collection": []}
    for tag in conn.execute(
        "select ns, value from shade_tag where shade_id = ? order by value", (shade_id,)
    ):
        tags[tag["ns"]].append(tag["value"])
    shade.update(status=status(shade), on_sale=on_sale(shade), images=images, tags=tags)
    return shade
