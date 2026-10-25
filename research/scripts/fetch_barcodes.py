"""One-off: fetch per-product JSON for every polish/top/base coat to see how many carry real GTINs.

Polite: one request per 1.2 s. Output: research/barcodes.json
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

root = Path(sys.argv[1])
products = []
for i in (1, 2, 3):
    products += json.loads((root / f"p{i}.json").read_text())["products"]
wanted = [p for p in products if p["product_type"] in ("Nail Polish", "Top Coat", "Base Coat", "Birthday Gift")]
out = {}
for p in wanted:
    req = urllib.request.Request(
        f"https://holotaco.com/products/{p['handle']}.json", headers={"User-Agent": "polished-research/0.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)["product"]
        out[p["handle"]] = [
            {"sku": v["sku"], "barcode": v["barcode"], "variant_id": v["id"]} for v in d["variants"]
        ]
    except Exception as e:  # noqa: BLE001
        out[p["handle"]] = {"error": str(e)}
    time.sleep(1.2)
(root / "barcodes.json").write_text(json.dumps(out, indent=1))
print(len(out))
