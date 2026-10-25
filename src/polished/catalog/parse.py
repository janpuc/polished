"""Reading a Shopify product: prices, tags, kind, topper flag, hero image, search text."""

import unicodedata
from decimal import Decimal, InvalidOperation

SHADE_KINDS = {"Nail Polish": "polish", "Top Coat": "topcoat", "Base Coat": "basecoat"}
TAG_NAMESPACES = ("finish", "color", "collection")
RETIRED_TAG = "collection:retirement"
RETIRING_TAG = "collection:soon-retiring"
CLEAR_TAG = "color:clear"
TOPPERS_TAG = "toppers"


def parse_price_cents(value: str | None) -> int | None:
    """ "15.50" -> 1550; None for a missing or unreadable price."""
    if value is None or value == "":
        return None
    try:
        return int((Decimal(str(value)) * 100).to_integral_value())
    except InvalidOperation:
        return None


def parse_compare_at_cents(value: str | None) -> int | None:
    """Like parse_price_cents, but 0 means "no compare-at price" and is stored as null."""
    return parse_price_cents(value) or None


def tag_pairs(tags: list[str]) -> list[tuple[str, str]]:
    """The finish:, color: and collection: tags as (namespace, value), duplicates dropped."""
    pairs: dict[tuple[str, str], None] = {}
    for tag in tags:
        ns, sep, value = tag.partition(":")
        if sep and ns in TAG_NAMESPACES and value:
            pairs[(ns, value)] = None
    return list(pairs)


def is_topper(kind: str, tags: list[str]) -> bool:
    """A top coat, or a polish Holo Taco tags `toppers` (the flakie, glow and glitter tacos,
    44 shades) or `color:clear` (which also catches the clear bases sticky-base and
    pink-smoothing-base; harmless in a layer picker)."""
    return kind == "topcoat" or (kind == "polish" and (TOPPERS_TAG in tags or CLEAR_TAG in tags))


def hero_image_url(images: list[dict]) -> str | None:
    """The bottle shot: the image at position 1, else the first one listed."""
    for image in images:
        if image.get("position") == 1:
            return image.get("src")
    return images[0].get("src") if images else None


def fold(text: str) -> str:
    """Lowercase and accent-folded, for searching."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def search_text(title: str, handle: str, tag_values: list[str]) -> str:
    """Title, the words of the handle and the tag values, folded and joined by spaces."""
    parts = [title, handle.replace("-", " ")] + [v.replace("-", " ") for v in tag_values]
    return fold(" ".join(parts))
