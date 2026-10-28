"""Which role a feed product plays: shade, bundle, alias or skipped (DESIGN 5.2, step 1)."""

import unicodedata
from dataclasses import dataclass

from .overrides import override_kind
from .parse import SHADE_KINDS

GIFT_TYPE = "Birthday Gift"
GIFT_SUFFIX = "-birthday-gift"

# Gift handles that do not name their shade: one has a trademark glyph, one a renamed shade.
MANUAL_ALIASES = {
    "linear-holo-taco\u2122-birthday-gift": "linear-holo-taco",
    "royal-tea-blue-birthday-gift": "royal-tea-blue-2021",
}


@dataclass(frozen=True)
class Classification:
    role: str  # shade | bundle | alias | skipped
    kind: str | None = None  # polish | topcoat | basecoat, for shades
    alias_source: str | None = None  # handle | manual, for aliases
    alias_target: str | None = None  # the shade handle an alias points at


def classify(product: dict) -> Classification:
    """First match wins. Gifts come before bundles because they carry bundle tags."""
    handle = unicodedata.normalize("NFC", product["handle"])
    product_type = product["product_type"]
    if handle in MANUAL_ALIASES:
        return Classification("alias", alias_source="manual", alias_target=MANUAL_ALIASES[handle])
    if product_type == GIFT_TYPE:
        return Classification(
            "alias", alias_source="handle", alias_target=handle.removesuffix(GIFT_SUFFIX)
        )
    if product_type not in SHADE_KINDS:
        return Classification("skipped")
    if any("bundle" in tag for tag in product["tags"]):
        return Classification("bundle")
    return Classification("shade", kind=override_kind(handle, SHADE_KINDS[product_type]))
