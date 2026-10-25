"""Reading a Shopify product: prices, tags, kind, topper flag, hero image, search text."""

import re
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


# Filename words that mark a shot as not showing the polish on a nail.
SWATCH_REJECT = ("bottle", "brush", "swipe", "corner", "side", "collage", "spill", "gif")
# Filename words by rank, best first: close-ups of one nail, then hands, then swatch shots, then
# (older products, whose files are numbered product-page shots) any page shot after the bottle.
SWATCH_RANKS = (("macro",), ("hand",), ("swatch", "nail", "mani", "ugc"), ("pdp", "layer"))
_WORD_PARTS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


def _words(text: str) -> list[str]:
    """Lowercase words of a filename or title: split on punctuation, camelCase and digits."""
    return [part.lower() for part in _WORD_PARTS.findall(text)]


def swatch_image_url(images: list[dict], title: str = "") -> str | None:
    """The photo that shows the polish on a nail, picked by filename (the feed has no alt text):
    skip bottle, brush and collage shots, then take the best rank, earliest position. Words are
    whole words (so "inside" is not "side"); the shade's own title words are dropped first (so
    "Bottle Service" is not a bottle shot). None when nothing qualifies; the app then crops the
    bottle shot."""
    title_words = _words(title)
    best: tuple[int, int, str] | None = None
    for index, image in enumerate(images):
        src = image.get("src")
        if not src:
            continue
        words = _words(src.split("?")[0].rsplit("/", 1)[-1])
        for start in range(len(words) - len(title_words) + 1 if title_words else 0):
            if words[start : start + len(title_words)] == title_words:
                del words[start : start + len(title_words)]
                break
        if any(w.startswith(r) for w in words for r in SWATCH_REJECT):
            continue
        for rank, keywords in enumerate(SWATCH_RANKS):
            if any(w.startswith(k) for w in words for k in keywords):
                if rank == 3 and (image.get("position") or index + 1) < 2:
                    break
                key = (rank, image.get("position") or index + 1, src)
                if best is None or key[:2] < best[:2]:
                    best = key
                break
    return best[2] if best else None


def fold(text: str) -> str:
    """Lowercase and accent-folded, for searching."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def search_text(title: str, handle: str, tag_values: list[str]) -> str:
    """Title, the words of the handle and the tag values, folded and joined by spaces."""
    parts = [title, handle.replace("-", " ")] + [v.replace("-", " ") for v in tag_values]
    return fold(" ".join(parts))
