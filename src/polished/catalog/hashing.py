"""Change detection: a hash of the fields the app shows (DESIGN 5.2, step 2)."""

import hashlib
import json

# Left out on purpose: the feed stamps every product with the sync time, so it says nothing
# about a change, and the description is large and never shown.
EXCLUDED_FROM_HASH = frozenset({"updated_at", "body_html"})


def content_hash(product: dict) -> str:
    """sha256 over canonical JSON of the hashed fields. Image `src` values embed `?v=<time>`,
    so a replaced photo changes the hash."""
    variant = product["variants"][0]
    fields = {
        "title": product["title"],
        "handle": product["handle"],
        "product_type": product["product_type"],
        "tags": sorted(product["tags"]),
        "sku": variant.get("sku"),
        "variant_id": variant["id"],
        "price": variant.get("price"),
        "compare_at_price": variant.get("compare_at_price"),
        "available": variant.get("available"),
        "published_at": product.get("published_at"),
        "images": [image["src"] for image in product.get("images", [])],
    }
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
