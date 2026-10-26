"""Finding shades: search, filters, sorting, pagination, status and the detail record
(DESIGN 5.3 and 6). Takes a connection; routes never write SQL."""

import json
import re
import sqlite3
from dataclasses import dataclass, field

from . import search as name_search
from .catalog.parse import fold
from .search import tokens

PAGE_SIZE = 40
SEARCH_LIMIT = 30

KINDS = ("polish", "topper", "base")
STATUSES = ("buyable", "retired", "sold_out")
OWNED = ("any", "owned", "not_owned", "wishlist")
SORTS = ("name", "newest", "released", "price")

# shade s left join product p left join shade_status ss. Same conditions as status() below, so a filter and a row's
# status never disagree (tests/test_shades.py checks it on every shade).
_LISTED = "s.source = 'holotaco' and p.missing_since is null"
STATUS_SQL = {
    "buyable": f"{_LISTED} and s.available = 1",
    "retired": f"{_LISTED} and s.retired = 1",
    "sold_out": f"{_LISTED} and s.retired = 0 and s.available = 0",
}
OWNED_SQL = {
    "owned": "ss.owned_count > 0",
    "not_owned": "ss.owned_count = 0",
    "wishlist": "ss.wishlisted = 1",
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
    "released": "s.released_on is null, s.released_on desc, s.title collate nocase, s.id",
    "price": "s.price_cents is null, s.price_cents, s.title collate nocase, s.id",
}

FROM = (
    "from shade s left join product p on p.id = s.product_id"
    " left join shade_status ss on ss.shade_id = s.id"
)


@dataclass(frozen=True)
class Status:
    key: str  # missing | retired | sold_out | retiring | available | sheet_only
    label: str
    buyable: bool


def status(shade) -> Status | None:
    """The state of a shade, first match wins (DESIGN 5.3). `shade` needs source, missing_since,
    retired, retiring and available (a row of the list or detail query). Manual shades have no
    status: nothing is known about a shop listing. A shade only the release sheet lists is "Not in
    the shop", whatever the sheet says about its retirement."""
    if shade["source"] == "manual":
        return None
    if shade["source"] == "sheet":
        return Status("sheet_only", "Not in the shop", False)
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
    owned: str = ""  # "" means any

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
        owned: str | None = None,
    ) -> "ShadeQuery":
        return cls(
            q=(q or "").strip()[:100],
            finish=tuple(dict.fromkeys(v for v in finish or [] if v)),
            color=tuple(dict.fromkeys(v for v in color or [] if v)),
            collection=(collection or "").strip(),
            kind=_pick(kind, KINDS),
            status=_pick(status, STATUSES),
            sort=_pick(sort, SORTS, "name"),
            owned=_pick(owned, OWNED[1:]),
        )

    def filter_count(self) -> int:
        """How many filters are on (the Filters button shows it); search and sort are not."""
        return (
            len(self.finish)
            + len(self.color)
            + bool(self.collection)
            + bool(self.kind)
            + bool(self.status)
            + bool(self.owned)
        )

    def params(self, page: int = 1) -> list[tuple[str, str]]:
        """Only what differs from the defaults, for a Load more URL."""
        pairs = [("q", self.q)] if self.q else []
        pairs += [("finish", v) for v in self.finish] + [("color", v) for v in self.color]
        for name in ("collection", "kind", "status", "owned"):
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
    fuzzy: bool = False  # a query with words, and some match needed typo tolerance


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
    if query.finish:
        _tag_clause("finish", query.finish, where, args)
    if query.color:
        _tag_clause("color", query.color, where, args)
    if query.collection:
        # An official collection name (the release sheet), or one of the shop's collection tags.
        where.append(
            "(s.official_collection = ? or exists (select 1 from shade_tag t"
            " where t.shade_id = s.id and t.ns = 'collection' and t.value = ?))"
        )
        args.extend((query.collection, query.collection))
    if query.kind:
        where.append(KIND_SQL[query.kind])
    if query.status:
        where.append(STATUS_SQL[query.status])
    if query.owned:
        where.append(OWNED_SQL[query.owned])
    return (" where " + " and ".join(where)) if where else "", args


def _order(query: ShadeQuery, owned_first: bool = False) -> str:
    """The home search and the pickers rank shades the household has first, then wishlisted ones
    (`owned_first`, DESIGN 6). A query with words is ranked by search.rank instead."""
    ranks = "(ss.owned_count > 0) desc, ss.wishlisted desc, " if owned_first else ""
    return ranks + ORDER_SQL[query.sort]


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


_COLUMNS = (
    "s.id, s.title, s.kind, s.source, s.hero_image_url, s.price_cents,"
    " s.compare_at_cents, s.available, s.retired, s.retiring, s.is_topper,"
    " s.swatch_hex, s.swatch_hex2, s.swatch_override_hex,"
    " p.missing_since, ss.owned_count, ss.wishlisted"
)


def list_shades(
    conn: sqlite3.Connection,
    query: ShadeQuery,
    page: int = 1,
    size: int = PAGE_SIZE,
    owned_first: bool = False,
) -> ShadePage:
    """One page of shades: rows with a Status, their finish values, the owned count and
    wishlist flag, and (for a query with words) `marks`, the spans of the title the words
    matched; and the total. A query with words ranks by relevance when sorted by name
    (search.rank); `owned_first` breaks ties there (same tier and title length) and orders a list
    without words."""
    page = max(page, 1)
    where, args = _where(query)
    offset = (page - 1) * size
    fuzzy = False
    if tokens(query.q):
        ranked_tiers = name_search.rank_with_tiers(conn, query.q, owned_first)
        ranked = [shade_id for shade_id, _ in ranked_tiers]
        if query.sort == "name":
            allowed = {r[0] for r in conn.execute(f"select s.id {FROM}{where}", args)}
            ids = [i for i in ranked if i in allowed]
        else:
            matched = set(ranked)
            ids = [
                r[0]
                for r in conn.execute(
                    f"select s.id {FROM}{where} order by {ORDER_SQL[query.sort]}", args
                )
                if r[0] in matched
            ]
        total = len(ids)
        listed = set(ids)
        fuzzy = any(tier == name_search.FUZZY for i, tier in ranked_tiers if i in listed)
        page_ids = ids[offset : offset + size]
        marks = ", ".join("?" * len(page_ids))
        by_id = {
            r["id"]: r
            for r in conn.execute(
                f"select {_COLUMNS} {FROM} where s.id in ({marks})", page_ids
            ).fetchall()
        }
        rows = [by_id[i] for i in page_ids]
    else:
        total = conn.execute(f"select count(*) {FROM}{where}", args).fetchone()[0]
        rows = conn.execute(
            f"select {_COLUMNS} {FROM}{where} order by {_order(query, owned_first)}"
            " limit ? offset ?",
            [*args, size, offset],
        ).fetchall()
    result = _with_finishes(conn, rows)
    if tokens(query.q):
        for row in result:
            row["marks"] = name_search.marks(row["title"], query.q)
    _add_lookalike_hints(conn, result)
    return ShadePage(rows=result, total=total, page=page, has_more=page * size < total, fuzzy=fuzzy)


def _add_lookalike_hints(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Gives each row whose name is all but the same as another row of the page a `hint` that
    tells them apart: the official collection, else the release year. Two names are alike when
    their words are equal or one letter apart."""
    keys = [" ".join(tokens(row["title"])) for row in rows]
    alike: set[int] = set()
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if name_search.distance(keys[i], keys[j], 1) <= 1:
                alike |= {rows[i]["id"], rows[j]["id"]}
    if not alike:
        return
    marks = ", ".join("?" * len(alike))
    facts = {
        r["id"]: r["official_collection"] or (r["released_on"] or "")[:4]
        for r in conn.execute(
            f"select id, official_collection, released_on from shade where id in ({marks})",
            list(alike),
        )
    }
    for row in rows:
        if row["id"] in alike and facts[row["id"]]:
            row["hint"] = facts[row["id"]]


def search(conn: sqlite3.Connection, text: str, limit: int = SEARCH_LIMIT) -> ShadePage:
    """The home typeahead: the first `limit` matches of a name search."""
    return list_shades(conn, ShadeQuery.from_params(q=text), size=limit, owned_first=True)


PICK_SCOPES = ("owned", "toppers", "all")


def pick(
    conn: sqlite3.Connection, text: str, scope: str = "owned", limit: int = SEARCH_LIMIT
) -> ShadePage:
    """The stack builder's picker: shades matching `text`, narrowed by `scope` (what the household
    owns, only toppers, or everything), owned shades first. An empty `text` lists the scope."""
    query = ShadeQuery.from_params(
        q=text,
        kind="topper" if scope == "toppers" else None,
        owned="owned" if scope == "owned" else None,
    )
    return list_shades(conn, query, size=limit, owned_first=True)


def facets(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """The values to offer as filters: finishes and colours most common first, the shop's
    collection tags alphabetical, and under `official` the release sheet's collection names
    alphabetical (empty until the sheet has been read)."""
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
    result["official"] = [
        r[0]
        for r in conn.execute(
            "select distinct official_collection from shade where official_collection is not null"
            " order by official_collection collate nocase"
        )
    ]
    return result


def get_shade(conn: sqlite3.Connection, shade_id: int) -> dict | None:
    """Everything the detail page shows: the shade, its status, tags by namespace, all product
    images (from the product's raw feed JSON), and the product handle for the shop link."""
    row = conn.execute(
        "select s.*, p.missing_since, p.raw_json, ss.owned_count, ss.bottle_count, ss.wishlisted"
        f" {FROM} where s.id = ?",
        (shade_id,),
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
    shade.update(
        status=status(shade),
        on_sale=on_sale(shade),
        images=images,
        tags=tags,
        shade_id=shade["id"],
        finishes=",".join(tags["finish"]),
    )
    return shade


HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


def set_tip_colour(conn: sqlite3.Connection, shade_id: int, colour: str | None) -> bool:
    """Saves the household's own tip colour ("#rrggbb"), or None to go back to the one read from
    the photos. The sync never writes this column. False for an unknown shade; ValueError for
    anything that is not a six-digit hex colour."""
    if colour is not None:
        if not HEX_COLOUR.fullmatch(colour):
            raise ValueError("Pick a colour.")
        colour = colour.lower()
    cursor = conn.execute(
        "update shade set swatch_override_hex = ? where id = ?", (colour, shade_id)
    )
    return cursor.rowcount == 1


MANUAL_KINDS = {  # form value -> (shade.kind, shade.is_topper)
    "polish": ("polish", 0),
    "topper": ("topcoat", 1),
    "base": ("basecoat", 0),
}


def create_manual(conn: sqlite3.Connection, title: str, kind: str) -> int:
    """A shade added by hand (a gifted bottle that is not in the catalog): no product, no price,
    no availability. `kind` is one of KINDS. Returns the shade id."""
    title = " ".join(title.split())
    if not title:
        raise ValueError("a shade needs a title")
    shade_kind, is_topper = MANUAL_KINDS[kind]
    cursor = conn.execute(
        "insert into shade (source, kind, title, search_text, is_topper)"
        " values ('manual', ?, ?, ?, ?)",
        (shade_kind, title, fold(title), is_topper),
    )
    return cursor.lastrowid
