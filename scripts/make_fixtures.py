"""Writes tests/fixtures/feed_trimmed.json from the local Shopify snapshot.

    python3 -I scripts/make_fixtures.py [SNAPSHOT_DIR [OUTPUT]]

SNAPSHOT_DIR holds p1.json, p2.json and p3.json (default: research/, untracked). The output is
committed: a handful of real products reduced to catalog fields (no body_html, two images),
chosen to cover the cases of docs/DESIGN.md section 5.4. One real shade, rest-in-peach, gets a
raised compare_at_price because no single shade is on sale in the real feed.
"""

import json
import sys
from pathlib import Path

# handle -> why it is in the fixture
PICKS = {
    "thirst-trap": "normal HL-*-NP polish with finish and colour tags, in stock",
    "thirst-trap-birthday-gift": "gift that merges onto thirst-trap by handle",
    "gold-play-button": "older HLT-NP-* polish, retired and sold out",
    "hit-the-lights": "sold out, not retired",
    "jam-session": "soon-retiring and sold out",
    "rest-in-peach": "soon-retiring, in stock; compare_at_price raised so it is on sale",
    "aurora-unicorn-skin": "Top Coat, a topper",
    "aurora-unicorn-skin-birthday-gift": "gift that merges onto a Top Coat by handle",
    "peely-base": "Base Coat",
    "sticky-base": "polish tagged color:clear, a topper",
    "brainrot-collection": "bundle (bundle:product)",
    "coastal-cremes-collection": "bundle whose only bundle tag is bundles-sets",
    "royal-tea-blue-2021": "target of a manual alias",
    "royal-tea-blue-birthday-gift": "gift that needs the manual alias",
    "linear-holo-taco™-birthday-gift": "manual-alias gift whose shade is not in the fixture",
    "super-magnet": "accessory, skipped",
}
RAISED_COMPARE_AT = {"rest-in-peach": "16.50"}
KEPT_IMAGES = 2


def trim(product: dict) -> dict:
    variant = product["variants"][0]
    return {
        "id": product["id"],
        "title": product["title"],
        "handle": product["handle"],
        "published_at": product["published_at"],
        "updated_at": product["updated_at"],
        "product_type": product["product_type"],
        "tags": product["tags"],
        "variants": [
            {
                "id": variant["id"],
                "sku": variant["sku"],
                "price": variant["price"],
                "compare_at_price": RAISED_COMPARE_AT.get(
                    product["handle"], variant["compare_at_price"]
                ),
                "available": variant["available"],
                "position": variant["position"],
            }
        ],
        "images": [
            {"position": image["position"], "src": image["src"]}
            for image in product["images"][:KEPT_IMAGES]
        ],
    }


def main() -> None:
    snapshot = Path(sys.argv[1] if len(sys.argv) > 1 else "research")
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "tests/fixtures/feed_trimmed.json")
    by_handle = {}
    for number in (1, 2, 3):
        page = json.loads((snapshot / f"p{number}.json").read_text(encoding="utf-8"))
        for product in page["products"]:
            by_handle[product["handle"]] = product
    missing = sorted(set(PICKS) - set(by_handle))
    if missing:
        sys.exit(f"not in the snapshot: {missing}")
    products = [trim(by_handle[handle]) for handle in PICKS]
    output.write_text(
        json.dumps({"products": products}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(products)} products to {output}")


if __name__ == "__main__":
    main()
