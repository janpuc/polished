"""The shapes of /api/v1 (docs/NATIVE.md 3). Every response model is here, so spec/api/openapi.yaml
(generated from them, see openapi.py) and the code cannot drift apart. Ids are opaque integers,
money is cents, dates are YYYY-MM-DD and timestamps are UTC (`…Z`)."""

from typing import Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(description="snake_case: bad_request, unauthorized, not_found, validation, …")
    message: str = Field(description="In the household's words, ready to show.")
    field: str | None = Field(None, description="The input at fault, for a validation error.")
    retry_after_s: int | None = Field(None, description="For a cooldown.")


class ErrorResponse(BaseModel):
    error: ErrorBody


# --- shared shapes -------------------------------------------------------------------------


class Tip(BaseModel):
    """The recipe of a painted nail tip; the app draws it (NATIVE.md 4). `revision` changes
    whenever the drawing would."""

    id: int = Field(description="The shade id, which seeds the random dust and glitter.")
    hex: str
    hex2: str | None
    finishes: list[str]
    topper: bool
    clear: bool
    coats: int
    colours: list[str]
    revision: str


class Status(BaseModel):
    key: Literal["missing", "retired", "sold_out", "retiring", "available", "sheet_only"]
    label: str
    buyable: bool


class ShadeRow(BaseModel):
    id: int
    title: str
    kind: Literal["polish", "topcoat", "basecoat"]
    source: Literal["holotaco", "manual", "sheet"]
    is_topper: bool
    price_cents: int | None
    compare_at_cents: int | None
    status: Status | None = Field(description="null for a shade added by hand.")
    finishes: list[str]
    owned_count: int
    wishlisted: bool
    hero_image_url: str | None
    released_on: str | None
    official_collection: str | None
    marks: list[list[int]] = Field(
        description="[start, end) spans of `title` the search words matched, as Unicode-scalar "
        "offsets (Python str indices; in Swift, index title.unicodeScalars). Empty without a query."
    )
    tip: Tip


class Bottle(BaseModel):
    id: int
    shade_id: int
    state: Literal["full", "half", "low", "empty"]
    printed_code: str | None
    bought_on: str | None
    price_paid_cents: int | None
    opened_on: str | None
    notes: str | None
    archived: bool
    created_at: str
    updated_at: str


class Layer(BaseModel):
    id: int
    ord: int = Field(description="1 is painted first (the base).")
    shade_id: int
    title: str
    coats: int
    label: str = Field(description="Base, 2nd, 3rd, …, Top; empty for a single layer.")
    tip: Tip


class Tile(BaseModel):
    position: int
    filled: bool
    has_draft: bool
    stack_id: int | None
    draft_stack_id: int | None
    summary: str
    layers: list[Layer]
    painted_on: str | None
    note: str | None


class Wheel(BaseModel):
    id: int
    slug: str
    name: str
    slot_count: int
    archived: bool
    filled: int
    drafts: int
    tag_url: str
    created_at: str


class WheelWithTiles(Wheel):
    tiles: list[Tile]


class WheelRef(BaseModel):
    id: int
    name: str
    slug: str


class WheelDetail(WheelWithTiles):
    filled_count: int
    others: list[WheelRef] = Field(description="The wheels whose tag this one could take.")


# --- auth ----------------------------------------------------------------------------------


class UserBrief(BaseModel):
    sub: str
    name: str


class User(UserBrief):
    first_name: str


class ExchangeRequest(BaseModel):
    code: str = Field(max_length=200)
    verifier: str = Field(max_length=128, description="The PKCE code verifier.")
    device_name: str = Field("", max_length=200)
    platform: str = Field("ios", max_length=40)
    app_version: str = Field("", max_length=40)


class ExchangeResponse(BaseModel):
    token: str = Field(description="Shown once. Send it as `Authorization: Bearer <token>`.")
    token_id: int
    user: UserBrief


class Device(BaseModel):
    id: int
    device_name: str
    platform: str
    created_at: str
    last_used_at: str | None
    current: bool


class Devices(BaseModel):
    items: list[Device]


# --- me, home ------------------------------------------------------------------------------


class ServerInfo(BaseModel):
    version: str
    public_url: str
    store_url: str
    timezone: str
    over_black_available: bool
    shade_count: int


class Me(BaseModel):
    user: User
    server: ServerInfo


class Wear(BaseModel):
    shade: ShadeRow
    bottle: Bottle
    worn_today: bool


class RecentBottle(BaseModel):
    bottle: Bottle
    shade: ShadeRow


class HomeCounts(BaseModel):
    bottles: int
    shades: int
    wished: int
    wished_cents: int


class Home(BaseModel):
    greeting_name: str
    date: str
    wear: Wear | None = Field(description="null until the wear log exists, or nothing is owned.")
    recent: list[RecentBottle]
    wheel: WheelWithTiles | None
    counts: HomeCounts


# --- shades --------------------------------------------------------------------------------


class ShadePage(BaseModel):
    items: list[ShadeRow]
    total: int
    page: int
    has_more: bool
    fuzzy: bool = Field(
        description="True when nothing matches the query by title or tag and the items are the "
        "typo-tolerant matches (the app may say 'Showing close matches')."
    )


class Facets(BaseModel):
    finish: list[str]
    color: list[str]
    collection: list[str]
    official: list[str]


class ShadeTags(BaseModel):
    finish: list[str]
    color: list[str]
    collection: list[str]


class WishlistEntry(BaseModel):
    id: int
    priority: Literal[1, 2, 3]
    note: str | None


class SwatchedOn(BaseModel):
    wheel_id: int
    slug: str
    name: str
    position: int
    stack_id: int


class ShadeDetail(BaseModel):
    shade: ShadeRow
    images: list[str]
    tags: ShadeTags
    sku: str | None
    handle: str | None
    store_url: str | None = Field(description="The shop page; null without a handle.")
    on_sale: bool
    bottles: list[Bottle]
    wishlist: WishlistEntry | None
    swatched_on: list[SwatchedOn]
    tip_source: Literal["override", "sampled", "none"]


# --- bottles -------------------------------------------------------------------------------


class BottleGroup(BaseModel):
    shade: ShadeRow
    bottles: list[Bottle]


class BottleGroups(BaseModel):
    groups: list[BottleGroup]


class HistoryRow(BaseModel):
    bottle: Bottle
    shade: ShadeRow
    dated_by_entry: bool = Field(description="True when the bottle has no bought_on date.")


class HistoryMonth(BaseModel):
    month: int
    label: str
    count: int
    total_cents: int
    unpriced: int
    rows: list[HistoryRow]


class HistoryYear(BaseModel):
    year: int
    count: int
    total_cents: int
    unpriced: int
    months: list[HistoryMonth]


class History(BaseModel):
    years: list[HistoryYear]


# --- wishlist ------------------------------------------------------------------------------


class WishlistItem(BaseModel):
    id: int
    shade: ShadeRow
    priority: Literal[1, 2, 3]
    note: str | None
    added_on: str
    buyable: bool


class WishlistSummary(BaseModel):
    count: int
    total_cents: int
    buyable_count: int
    buyable_cents: int


class Cart(BaseModel):
    url: str | None = Field(description="The shop's cart permalink; null when nothing is buyable.")
    total_cents: int
    count: int
    skipped: int = Field(description="Wanted shades that cannot be bought now.")
    names: list[str]


class Wishlist(BaseModel):
    items: list[WishlistItem]
    summary: WishlistSummary
    cart: Cart


# --- lookup, identifiers -------------------------------------------------------------------


class LookupShade(ShadeRow):
    images: list[str]


class LookupResults(BaseModel):
    items: list[ShadeRow]
    total: int


class Lookup(BaseModel):
    outcome: Literal[
        "match", "suggestion", "unknown_code", "unknown_printed", "invalid_code", "results"
    ]
    code: str | None = Field(description="The normalised barcode or P code.")
    kind: Literal["gtin", "printed", "sku"] | None
    shade: LookupShade | None
    identifier_id: int | None = Field(description="The learned code a match came from.")
    results: LookupResults | None


class Identifier(BaseModel):
    id: int
    kind: Literal["gtin", "printed"]
    value: str
    shade: ShadeRow
    use_count: int
    created_at: str
    last_used_at: str | None


class Identifiers(BaseModel):
    items: list[Identifier]


# --- wheels, stacks ------------------------------------------------------------------------


class Wheels(BaseModel):
    items: list[WheelWithTiles]


class StackWheel(BaseModel):
    id: int
    slug: str
    name: str


class StackSheet(BaseModel):
    stack_id: int
    wheel: StackWheel
    position: int
    name: str | None
    note: str | None
    painted_on: str | None
    layers: list[Layer]
    summary: str
    full: bool
    tip: list[Tip] = Field(description="The composite recipe: the layers' tips in painting order.")


class CopySource(BaseModel):
    stack_id: int
    wheel_name: str
    wheel_slug: str
    position: int
    name: str | None
    painted_on: str | None
    summary: str
    layers: list[Layer]


class CopySources(BaseModel):
    items: list[CopySource]


class Pick(BaseModel):
    items: list[ShadeRow]
    total: int
    suggestion: ShadeRow | None = Field(
        description="The shade a typed P code or barcode is known to be; show it first."
    )


# --- sync ----------------------------------------------------------------------------------


class SyncRun(BaseModel):
    id: int
    started_at: str
    finished_at: str | None
    status: Literal["running", "ok", "error"]
    trigger: Literal["schedule", "catchup", "manual", "cli"]
    pages_fetched: int
    products_seen: int
    new_shades: int
    changed_shades: int
    newly_missing: int
    returned: int
    unresolved_aliases: int
    error: str | None


class Sync(BaseModel):
    running: bool
    last: SyncRun | None
    runs: list[SyncRun] = Field(description="The latest ten, newest first.")
    cooldown_until: str | None = Field(description="When Sync now is allowed again; null if now.")
