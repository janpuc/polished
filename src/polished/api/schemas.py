"""The shapes of /api/v1 (docs/NATIVE.md 3). Every response model is here, so spec/api/openapi.yaml
(generated from them, see openapi.py) and the code cannot drift apart. Ids are opaque integers,
money is cents, dates are YYYY-MM-DD and timestamps are UTC (`…Z`)."""

from typing import Literal

from pydantic import BaseModel, Field


def one_of(*values, default=...):
    """A field that takes one of `values`. The type stays str or int so the answer to a wrong
    value is the web's sentence (written by the route), not a validation message of pydantic's."""
    allowed = [*values, None] if default is None else list(values)
    return Field(default, json_schema_extra={"enum": allowed})


class ErrorBody(BaseModel):
    code: str = Field(description="snake_case: bad_request, unauthorized, not_found, validation, …")
    message: str = Field(description="In the household's words, ready to show.")
    field: str | None = Field(None, description="The input at fault, for a validation error.")
    fields: dict[str, str] | None = Field(
        None, description="Every wrong input and its message, when more than one is wrong."
    )
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
    bottle: Bottle = Field(
        description="The newest bottle of the shade that is not archived or empty."
    )
    worn_today: bool


class Worn(BaseModel):
    worn_on: str = Field(description="The household's date, YYYY-MM-DD.")


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
    wear: Wear | None = Field(
        description="Today's pick, the same all day; the shade worn today once one was. "
        "null when nothing is owned."
    )
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
    outcome: Literal["match", "unknown_code", "invalid_code", "results"]
    code: str | None = Field(description="The normalised barcode or SKU.")
    kind: Literal["gtin", "sku"] | None
    shade: LookupShade | None
    identifier_id: int | None = Field(description="The learned code a match came from.")
    results: LookupResults | None


class Identifier(BaseModel):
    id: int
    kind: Literal["gtin"]
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


# --- writes --------------------------------------------------------------------------------
# Request bodies and the answers only writes give. A wrong value is a 422 `validation` with the
# web's sentence and `field` set; fields left out of a PATCH keep their value.


class ManualShadeRequest(BaseModel):
    title: str = Field(max_length=500, description="Cut to 100 characters.")
    kind: str = one_of("polish", "topper", "base")


class TipColourRequest(BaseModel):
    hex: str | None = Field(description='"#rrggbb", or null to go back to the sampled colour.')


class BottleRequest(BaseModel):
    state: str = one_of("full", "half", "low", "empty", default="full")
    bought_on: str | None = Field(None, description="YYYY-MM-DD, not in the future.")
    price_paid_cents: int | None = None
    opened_on: str | None = Field(None, description="YYYY-MM-DD, not in the future.")
    notes: str | None = Field(None, description="Cut to 500 characters.")


class BottlePatch(BaseModel):
    """Any subset of the bottle's fields; null clears the optional ones."""

    state: str | None = one_of("full", "half", "low", "empty", default=None)
    bought_on: str | None = None
    price_paid_cents: int | None = None
    opened_on: str | None = None
    notes: str | None = None
    archived: bool | None = None


class BottleCreated(BaseModel):
    bottle: Bottle


class WishlistAdd(BaseModel):
    priority: int = one_of(1, 2, 3, default=2)


class WishlistPatch(BaseModel):
    priority: int | None = one_of(1, 2, 3, default=None)
    note: str | None = Field(None, description="Cut to 200 characters; null or empty clears it.")


class BoughtItem(BaseModel):
    id: int
    price_cents: int | None = None


class BoughtRequest(BaseModel):
    items: list[BoughtItem]
    bought_on: str | None = Field(None, description="YYYY-MM-DD, not in the future; default today.")


class Bought(BaseModel):
    bottles: list[Bottle] = Field(description="One new full bottle per item, in the order given.")
    wishlist: Wishlist


class IdentifierRequest(BaseModel):
    kind: str = one_of("gtin")
    value: str = Field(max_length=100)
    shade_id: int


class IdentifierBrief(BaseModel):
    id: int
    kind: Literal["gtin"]
    value: str
    shade_id: int


class IdentifierLearned(BaseModel):
    identifier: IdentifierBrief
    created: bool = Field(
        description="False when the code was already known: it keeps the shade it had, which "
        "`identifier.shade_id` and `shade` show."
    )
    shade: ShadeRow


class WheelRequest(BaseModel):
    name: str = Field(max_length=500, description="Cut to 60 characters.")
    slot_count: int = Field(20, description="1 to 40.")


class WheelPatch(BaseModel):
    name: str | None = None
    archived: bool | None = None


class WheelDeleted(BaseModel):
    deleted_swatches: int


class TakeTagRequest(BaseModel):
    from_wheel_id: int


class StackOpened(StackSheet):
    resumed: bool = Field(description="True when the slot already had a draft.")


class LayerRequest(BaseModel):
    shade_id: int


class LayerPatch(BaseModel):
    """One of the two."""

    coats_delta: int | None = one_of(-1, 1, default=None)
    move: str | None = one_of("up", "down", default=None)


class TemplateRequest(BaseModel):
    kind: str = one_of("over_black", "copy", "last")
    source_stack_id: int | None = Field(None, description="For `copy`: a saved stack.")


class StackTemplated(StackSheet):
    result: Literal["added", "already", "unavailable", "copied", "nothing_saved"] = Field(
        description="`over_black`: added, already (nothing changed) or unavailable (the catalog has "
        "no black base). `copy`: copied. `last`: copied, or nothing_saved (the draft is untouched)."
    )


class SaveRequest(BaseModel):
    name: str | None = Field(None, description="Cut to 80 characters.")
    note: str | None = Field(None, description="Cut to 500 characters.")
    painted_on: str | None = Field(
        None, description="YYYY-MM-DD, not in the future; default today."
    )


class SlotResult(BaseModel):
    wheel_id: int
    position: int
    tile: Tile


class SyncStarted(BaseModel):
    run_id: int
