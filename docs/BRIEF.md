# polished: brief

A nail polish inventory for one household, hosted on Jan's home-ops cluster. The main user buys only
from holotaco.com. The app has to answer two questions quickly, on a phone: "do I already have
this?" and "what do I still want?"

## Users and use

- Two people: the main user and Jan. Mostly a phone, sometimes a laptop.
- She owns somewhere in the tens to low hundreds of bottles. The catalog holds about 420 shades.
- Bottles carry a printed ID such as `P123` and a barcode. We don't yet know how either maps to
  the catalog; see Open questions.

## Verified facts (2026-10-25)

### holotaco.com is a public Shopify store

- `GET https://holotaco.com/products.json?limit=250&page=N` returns the catalog without auth: 526
  products over 3 pages.
- `product_type`: Nail Polish 405, Birthday Gift 71, Accessories 24, Top Coat 9, Base Coat 4,
  Gift Card 4, Free Gift 3, Nail Care 2, others 1-2. "Birthday Gift" entries are loyalty copies
  of real shades (for example `im-over-brew-birthday-gift`) and have to be merged into the
  real shade or skipped.
- Every polish has one variant. `variants[].available` is true for 240 and false for 178 (sold
  out or retired). Retired shades stay listed, tagged `collection:retirement`, though some may
  drop out of the feed entirely, so the app must keep every shade it has ever seen.
- Tags are structured: `finish:<x>` (holographic, shimmer, iridescent, creme, metallic, glitter,
  jelly, flakie, chrome, magnetic, thermal, matte, ...), `color:<x>` (blue, purple, pink,
  green, red, ...), `collection:<x>` (brainrot, holographic, limited-edition, retirement, ...).
  Bundles carry `bundle:product` / `product-bundle` and are not single shades.
- SKU patterns: `HL-00478-NP` (287, newer), `HT-00xxx-ST` (38, sets?), `HLT-NP-0719-TOPP-B04-R`
  (older), and some bundles use plain numeric SKUs.
- `GET https://holotaco.com/products/<handle>.json` adds `variants[].barcode`, which
  `products.json` lacks. It is inconsistent: `one-coat-black` has a real UPC `810170280160`
  (GS1 prefix 810170, presumably Holo Taco's); the 2026 Brainrot shades have 9-digit numbers
  such as `795203598` that look Shopify-internal and probably don't match the printed barcode.
  So barcode → shade must be **learned** on first scan, seeded from catalog barcodes that are
  valid GTINs.
- Images: about 9 per shade on cdn.shopify.com. Position 1 is the bottle hero; later images are
  hand swatches, macros and "spill" shots (file names say which). These are the raw material
  for colour data.
- Shopify cart permalinks (`https://holotaco.com/cart/<variant_id>:<qty>,...`) can open a
  pre-filled cart from the wishlist. Not yet tested against this store.
- Be polite: a daily sync of 3 `products.json` pages at 1 request per second at most. (Superseded:
  per-product fetches and `updated_at` change detection were dropped; see DESIGN.md sections 5
  and 14.)

### home-ops conventions (janpuc/home-ops, read-only for agents)

- Flux + bjw-s `app-template` HelmRelease; app dir `kubernetes/apps/<ns>/<app>/{ks.yaml,app/}`
  with `ocirepository.yaml`, `helmrelease.yaml`, `kustomization.yaml`, optional
  `externalsecret.yaml`, `pocketidoidcclient.yaml`.
- Household apps: `mealie` (selfhosted ns) runs SQLite on a PVC backed up by the
  `components/kopiur/backup` component, and logs in through Pocket ID OIDC
  (`https://id.janpuc.com`, groups `ID-Users` / `ID-Admin`). `spoolman` (home ns, filament
  inventory) is the closest analogue and sits on `envoy-internal` at `spoolman.janpuc.com`.
- Pocket ID clients are declared as `PocketIDOIDCClient` (operator writes client id/secret to a
  Secret); see `kubernetes/apps/ai/austerity-watcher/app/pocketidoidcclient.yaml`.
- Routes: Gateway API `route:` in app-template, `envoy-internal` (LAN/VPN) or `envoy-external`
  (Cloudflare tunnel), hostnames `*.janpuc.com`.
- Custom images: `ghcr.io/janpuc/<app>`, built by GitHub Actions with release-please (see
  `~/Development/serendip/.github/workflows/release.yml`, `Dockerfile`,
  `release-please-config.json`, `.renovaterc.json5`). Pods run as uid 1000 with a read-only
  root filesystem and `/data` as the writable volume.
- In-cluster LLMs: LiteLLM at `http://litellm.ai.svc.cluster.local:4000/v1`. Vision-capable
  and local: `m3pro-local/huihui-qwen3.8-27b` (M3 Pro, ~9 tok/s, one request at a time, 32K
  context). Private material stays on `*-local` aliases.
- Jan's own stack for these apps: Python 3.12, uv, FastAPI, httpx, ruff, pytest, SQLite.

## Ideas (to be ranked)

- Catalog sync from holotaco.com: new releases, price, availability, retirement.
- Inventory: one shade can have several bottles; per-bottle state (full / half / low / empty),
  purchase date, price, opened date, notes.
- Wishlist with priority; total cost; "open this in a Holo Taco cart" via permalink.
- Barcode scanning in the phone browser (BarcodeDetector where it exists, a WASM fallback for
  iOS Safari). Unknown barcode → pick the shade once → mapping saved.
- Swatch identification:
  - Photo of a bottle → which shade (barcode first, then vision LLM reading the label against
    the catalog list).
  - Dupe check: "you already own 3 shades close to this" before buying (colour distance in
    CIELAB over colours taken from catalog swatch images, plus finish match).
  - Photo of a mani → closest owned shades.
- Alerts: a wishlist shade is back in stock, on sale, or retiring; new collection dropped.
- Swatch wheels (from Jan, 2026-10-25): The main user paints swatches on wheels of 20 nail tips. Jan has
  NFC tags and can stick one on each wheel. Tapping a wheel with a phone opens that wheel in
  the app: which shade sits in which slot (1-20), free slots, and "where is the swatch of shade
  X" (wheel 4, slot 12). iPhone and Android both open NFC URL tags natively; writing tags from
  the browser (Web NFC) only works in Android Chrome, otherwise with an app such as NFC Tools.
  A wheel photo could also supply her real swatch colours per slot, which beat catalog photos
  for colour matching.
- Layers (from Jan, 2026-10-25): a swatch is not always one shade. A nail can be an ordered
  stack, e.g. 1 coat of a base shade, then a topper (flakie, glitter) on top. Wheel slots and
  mani log entries hold an ordered list of layers (shade, coats, order), and "where did I use
  topper X" has to find every stack it is in. Toppers are often swatched over black.
- Collection progress ("5/8 of Brainrot").
- Mani log: what was worn when, with a photo; "not worn in a while"; random mani picker.
- Read-only shareable wishlist for gift ideas.

## Answers from Jan (2026-10-25)

1. Printed ID: Spirit Fingers is `P259`. Its catalog SKU is `HL-00169-NP`, so the P number does
   **not** follow the SKU digits. Treat it as a learned code → shade mapping, like barcodes.
   Spirit Fingers' catalog barcode is `810065564276`, a valid UPC-A with a different GS1 prefix
   (810065), so catalog barcodes are real for at least some shades. Still to confirm against the
   bottle.
2. iPhone only: no BarcodeDetector in Safari (WASM ZXing it is), no Web NFC (tags are written
   with an app such as NFC Tools; reading URL tags works natively).
3. Reachable from anywhere, behind Pocket ID. The main user has a Pocket ID account.
4. Layers are free-form: any shade over any other, any number of layers, in order. Jan: "that's
   going to be the best part of the system, it's hard to write it down and remember". Picking
   x + y + z in order has to be intuitive on a phone.
5. The repo can be public (janpuc/polished).

6. The Spirit Fingers bottle's barcode reads `810170284120` (valid UPC-A, Holo Taco's 810170
   prefix), **not** the catalog's `810065564276`. Catalog barcodes cannot be trusted as the
   bottle's barcode; the learned mapping is the primary path. Only one Spirit Fingers bottle
   exists, so whether P numbers are per shade or per batch stays unknown.

## Open questions

1. Is `P259` the same on every Spirit Fingers bottle (a shade code) or per batch? Store it per
   bottle and treat a learned P → shade mapping as a suggestion, not a fact.

## Working rules

- Never touch the live cluster or push home-ops. Prepare home-ops changes on a branch and hand
  Jan the diff.
- Never create the GitHub repo or push without Jan's yes.
- Work in stages; report after each.
