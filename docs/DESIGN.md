# polished: design

Status: plan, nothing built yet. Goal, users and Jan's answers are in `BRIEF.md`; the advisor's
recommendation is in `advice/fable-2026-10-25.md` and is the baseline. Where this document
differs from the advice, section 14 says so. The build order is in `PLAN.md`.

polished answers two questions on a phone: **"do I already have this?"** and **"what do I still
want?"**, and keeps the part Jan calls the best of it: **free-form layer stacks** (any shade
over any other, in painting order) on swatch wheels that open from an NFC tag or QR code.

## 1. Scope

**v1** (this document specifies it fully)

- Catalog sync from holotaco.com: shades, availability, price, retirement.
- Shade browse, search and filters (finish, colour, collection, kind, status, owned).
- Bottles: several per shade, state, printed P code, purchase details.
- Wishlist: priority, total, a Shopify cart permalink.
- Identifier lookup: barcode scan (zxing-wasm), typed P code, learned mappings.
- Layer stacks: bottom-sheet builder, templates "over black" and "copy from".
- Swatch wheels (20 slots by default), one URL per wheel for an NFC tag or QR sticker.
- Pocket ID OIDC login, PWA shell.

**v2** (sketched in section 4.4): colour extraction and dupe check, price/stock observations,
alerts (in-app feed, daily Matrix digest through a webhook notifier), collection progress,
read-only share link, vision-LLM fallback.

**v3**: mani log with photos, tap-to-sample colours, random picker.

**Never**: an SPA, CLIP embeddings, automatic wheel detection, Web NFC writing, offline writes.

## 2. Verified catalog facts

Checked on 2026-10-25 against `research/p1.json`, `p2.json`, `p3.json` (pages of 250, 250 and 26
products) and `research/barcodes.json`. Appendix A reproduces every number.

| Fact | Value |
|---|---|
| Products in the feed | 526 (unique ids and handles; exactly one variant each; ids are up to 14 digits, so they fit SQLite integers) |
| `product_type` | Nail Polish 405, Birthday Gift 71, Accessories 24, Top Coat 9, Base Coat 4, Gift Card 4, Free Gift 3, Nail Care 2, Hats 2, two others 1 each |
| Bundles | 46 Nail Polish products with any tag containing `bundle` (`bundle:product` alone matches 37, `product-bundle` 37, six more carry only `bundles-sets`, two `bundle:top-shelf`). Five have numeric SKUs, 38 have `HT-xxxxx-ST`, so SKUs cannot classify |
| Single shades | **372** = 359 polish + 9 top coat + 4 base coat. No Top Coat or Base Coat carries a bundle tag |
| Classification totals | 372 shades + 46 bundles + 71 birthday gifts + 37 skipped = 526 |
| SKU shapes of the 372 | 285 `HL-NNNNN-NP` (284 polish + 1 base coat), 74 polish `HLT-NP-MMYY-…`, 1 polish `HLT-BT-1120-TPBA-T01-R` (`matte-taco`), 12 top/base coats `HLT-NP-…`/`HLT-BT-…`. All 372 SKU strings are unique today, but Shopify does not enforce that, so the schema does not either |
| Birthday gifts | 71. Handle = `<shade handle>-birthday-gift`. **69 merge by handle** (68 onto polish, 1 onto Top Coat `aurora-unicorn-skin`); 2 need the manual alias list: `linear-holo-taco™-birthday-gift` (trademark glyph in the handle) and `royal-tea-blue-birthday-gift` → `royal-tea-blue-2021`. Gift SKUs (`HL-NNNNN-HB`) coincide with a shade's `HL-NNNNN-NP` number only 34 times of 70, so SKU digits never merge anything. Gifts also carry `product-bundle` and `bundle:product` tags: classification must test `product_type` first |
| Availability of the 372 | 208 buyable, 164 not |
| Retired (`collection:retirement`) | 118 (116 unavailable, 2 still buyable: `reflective-taco`, `everything-taco`) |
| Retiring (`collection:soon-retiring`) | 14 (13 unavailable, 1 buyable: `rest-in-peach`; one is also tagged retired) |
| Sold out, not retired | 48 (12 of them also soon-retiring) |
| Sale (`price < compare_at_price`) | **0 single shades today.** The 44 on sale are all bundles. `compare_at_price` equals the price for 365 shades and is *below* the price on 6, so only a strict `price < compare_at` counts as a sale |
| Prices | strings such as `"15.50"`; currency is not in the feed (USD assumed) |
| `updated_at` | `2026-10-25` on all 526 products: useless as a change signal |
| Tags on shades | `finish:` on 346 (13 values), `color:` on 361 (25 values), `collection:` on all 372 (67 values). 26 shades have no finish tag, 11 no colour |
| Toppers | 9 `Top Coat` products, plus polish tagged `color:clear`: 14 shades carry that tag (1 Top Coat, 3 Base Coats, 10 listed as polish, two of those clear bases: `sticky-base`, `pink-smoothing-base`) |
| Images | 3 to 20 per shade (median 10), all on `cdn.shopify.com`, `position` 1 is the bottle hero, every `src` carries `?v=<timestamp>`, `alt` is null on all 6096 images |
| Catalog barcodes (per-product `.json`, 488 fetched, 1 failed) | 362 valid GTINs (12 digits; prefixes 810170 ×264, 810065 ×88, 850017 ×10), 126 nine-digit values that fail the check. One valid value is shared by two products. **The Spirit Fingers bottle reads `810170284120`, which is not in the catalog at all** (catalog says `810065564276`) |

Consequence for identification: catalog barcodes cannot identify a bottle, so they are neither
fetched nor stored (section 7).

## 3. Architecture

One container, one process, one SQLite file.

```
iPhone Safari / PWA ──https──> Cloudflare tunnel ──> envoy-external ──> polished :8080
                                                                          │
   Pocket ID (id.janpuc.com) <── OIDC, authlib ───────────────────────────┤
   holotaco.com  <── httpx, 3 requests/day, ≥1 s apart ───────────────────┤ (in-process sync task)
                                                                          │
                                                          /data/polished.db (PVC, kopiur backup)
```

- **FastAPI + Jinja2 + HTMX.** Pages are server-rendered. HTMX swaps partials; every mutation is
  a POST that returns the re-rendered partial, so there is no client-side state to lose.
- **JS islands** are plain ES modules under `static/js/`, loaded only on pages that need them:
  `scanner.js` (camera and zxing-wasm), `sheet.js` (opens and closes the bottom-sheet
  `<dialog>`, refocuses the picker field), `tag.js` (copy the tag URL). No bundler, no Node.
- **Vendored static assets** in `static/vendor/`: `htmx.min.js` and `zxing-wasm` (reader build:
  one ES module plus `zxing_reader.wasm`). Versions recorded in `static/vendor/VERSIONS.txt`, fetched by `scripts/vendor.sh` (a developer step);
  Renovate cannot update vendored files, so a refresh is a manual stage.
- **SQLite** through stdlib `sqlite3`: WAL, `foreign_keys=on`, `busy_timeout=5000`, one
  connection per request (FastAPI sync route functions run in the threadpool) and one for the
  sync task. One uvicorn worker only: the scheduler and the DB assume a single process.
  Numbered SQL migrations ship inside the package and run from an init container.
- **Dependencies:** fastapi, uvicorn[standard], jinja2, python-multipart, httpx, authlib,
  itsdangerous (session cookie), pydantic-settings, segno (QR, pure Python), tzdata.
  Dev: pytest, pytest-asyncio, ruff. Pillow and numpy arrive with v2 colour work, not before.
- **Time:** timestamps are UTC ISO-8601 text (`2026-10-25T04:05:38Z`), dates are `YYYY-MM-DD`
  in the household timezone (`POLISHED_TIMEZONE`, default `Europe/Warsaw`). Money is integer
  cents, rendered with `$`.
- **No per-user data.** One shared household collection. The session holds the Pocket ID
  subject and display name; nothing else about a person is stored.

### 3.1 Module layout (`src/polished/`)

```
__init__.py          __version__ = "0.1.0"  # x-release-please-version
__main__.py, cli.py  python -m polished {serve | migrate | sync [--from-files …]}
config.py            Settings (pydantic-settings, env prefix POLISHED_), section 12
db.py                connect(path), request-scoped connection dependency, transaction helper
migrate.py           numbered-SQL runner (serendip's, schema_version table)
migrations/          001_catalog.sql 002_inventory.sql 003_identifiers.sql 004_wheels_stacks.sql
server.py            create_app(): middleware order, routers, templates, static, lifespan
web.py               Jinja environment, render(): full page vs partial, filters (money, thumb, dates)
security.py          Origin check for unsafe methods, security headers and CSP, cache headers
auth.py              OIDC client, /auth/* routes, session helpers, deny-by-default gate
catalog/
  classify.py        product → shade | bundle | alias | skipped (+ MANUAL_ALIASES)
  parse.py           price parsing, tag splitting, shade kind, is_topper, hero image
  hashing.py         content_hash()
  fetch.py           polite Shopify client: fetch_feed(), rate limiter, User-Agent, 429 handling
  sync.py            run_sync(): apply the feed in one transaction, absence accounting, sync_run row
  scheduler.py       next_run_at(), background loop, startup catch-up, single-flight
shades.py            list/filter/search queries, status derivation, detail, manual shades
bottles.py           bottle CRUD, owned rules
wishlist.py          wishlist CRUD, totals, cart permalink
gtin.py              normalise_gtin(), check digit
identifiers.py       resolve(), learn(), printed-code normalisation
stacks.py            draft/commit, layers, templates, summary(), default_coats()
wheels.py            wheel CRUD, slug generation, slot grid, tag URL, QR
routes/              home.py shades.py bottles.py wishlist.py lookup.py wheels.py stacks.py
                     sync.py pwa.py health.py   (thin: parse, call domain function, render)
templates/           base.html, pages, partials/ (leading underscore: _shade_row.html …)
static/              css/app.css, js/, vendor/, icons/
```

Domain modules hold the SQL and take a connection; routes never write SQL. This keeps stage
tests (`tests/test_<module>.py`) independent of HTTP.

### 3.2 Page versus partial

`render()` returns a partial when the request has `HX-Request: true` and does **not** have
`HX-History-Restore-Request`; otherwise the full page. History restore must be a full page, and
`htmx-config` sets `historyCacheSize: 0` so private pages are not snapshotted into localStorage
and `includeIndicatorStyles: false` so HTMX injects no inline `<style>` (the CSP forbids it).
All HTML responses carry `Cache-Control: private, no-cache` and `Vary: HX-Request,
HX-History-Restore-Request`, so Safari's back button never shows a partial.

## 4. Data model

SQLite DDL. Own integer primary keys everywhere; Shopify ids are columns. One migration file per
stage that needs tables; each file runs inside a transaction. Statements are written so the
whole block (4.1 to 4.3) loads into an empty database in order.

### 4.1 `001_catalog.sql`

```sql
-- 001_catalog.sql: what the feed told us (stage 1).

-- Every product the feed ever listed (526 today). Rows are never deleted.
create table product (
  id                 integer primary key,
  shopify_product_id integer not null unique,
  variant_id         integer not null,            -- variants[0]; every product has exactly one
  handle             text not null,               -- may change; identity is shopify_product_id
  title              text not null,
  product_type       text not null,
  role               text not null check (role in ('shade', 'bundle', 'alias', 'skipped')),
  sku                text,
  price_cents        integer,
  compare_at_cents   integer,                     -- null when absent or 0
  available          integer not null check (available in (0, 1)),
  published_at       text,
  tags_json          text not null,               -- the feed's tag array, as sent
  raw_json           text not null,               -- the product minus body_html, kept when the hash changes
  content_hash       text not null,
  first_seen         text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_seen          text not null,
  absent_syncs       integer not null default 0,  -- consecutive successful syncs without it
  missing_since      text                         -- set at absent_syncs >= 3, cleared when it returns
);
create index product_handle on product (handle);
create index product_role on product (role);

-- One row per real single polish, topper or base coat (372 today), plus manual shades.
-- The app-facing copy of the product's facts, so queries need no join.
create table shade (
  id               integer primary key,
  product_id       integer unique references product (id),   -- null for source = 'manual'
  source           text not null default 'holotaco' check (source in ('holotaco', 'manual')),
  kind             text not null check (kind in ('polish', 'topcoat', 'basecoat')),
  title            text not null,
  handle           text,
  sku              text,                                      -- not unique: Shopify does not enforce it
  search_text      text not null,                             -- lowercase, accent-folded title + tag values
  hero_image_url   text,                                      -- images[position = 1].src
  price_cents      integer,
  compare_at_cents integer,
  available        integer check (available in (0, 1)),       -- null for manual shades
  published_at     text,
  is_topper        integer not null default 0,                -- topcoat, or polish tagged color:clear
  retired          integer not null default 0,                -- tag collection:retirement
  retiring         integer not null default 0,                -- tag collection:soon-retiring
  created_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
create index shade_kind on shade (kind);
create index shade_sku on shade (sku);
create index shade_handle on shade (handle);

-- Birthday-gift copies (and renamed or relisted products) pointing at the canonical shade.
create table shade_alias (
  product_id integer primary key references product (id),
  shade_id   integer not null references shade (id),
  source     text not null check (source in ('handle', 'manual'))
);
create index shade_alias_shade on shade_alias (shade_id);

-- finish:x, color:x, collection:x as rows (not a comma string): filters and collection
-- progress query these.
create table shade_tag (
  shade_id integer not null references shade (id) on delete cascade,
  ns       text not null check (ns in ('finish', 'color', 'collection')),
  value    text not null,
  primary key (shade_id, ns, value)
) without rowid;
create index shade_tag_lookup on shade_tag (ns, value);

-- One row per sync attempt: the /sync page, the manual-sync cooldown, startup catch-up.
create table sync_run (
  id                 integer primary key,
  started_at         text not null,
  finished_at        text,
  trigger            text not null check (trigger in ('schedule', 'catchup', 'manual', 'cli')),
  status             text not null check (status in ('running', 'ok', 'error')),
  pages_fetched      integer not null default 0,
  products_seen      integer not null default 0,
  new_shades         integer not null default 0,
  changed_shades     integer not null default 0,
  newly_missing      integer not null default 0,
  returned           integer not null default 0,
  unresolved_aliases integer not null default 0,
  error              text
);
```

### 4.2 `002_inventory.sql` (stage 4)

```sql
-- 002_inventory.sql: what is owned and what is wanted.

create table bottle (
  id               integer primary key,
  shade_id         integer not null references shade (id),
  printed_code     text,                                      -- the P number as printed, normalised ("P259")
  state            text not null default 'full' check (state in ('full', 'half', 'low', 'empty')),
  bought_on        text,
  price_paid_cents integer,
  opened_on        text,
  notes            text,
  archived         integer not null default 0 check (archived in (0, 1)),
  created_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at       text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
create index bottle_shade on bottle (shade_id);
create index bottle_printed_code on bottle (printed_code);

create table wishlist_item (
  id       integer primary key,
  shade_id integer not null unique references shade (id),
  priority integer not null default 2 check (priority between 1 and 3),   -- 1 = want most
  note     text,
  added_on text not null default (date('now'))
);

-- Owned = at least one bottle that is not archived and not empty.
create view shade_status as
select s.id as shade_id,
       (select count(*) from bottle b
         where b.shade_id = s.id and b.archived = 0 and b.state <> 'empty') as owned_count,
       (select count(*) from bottle b where b.shade_id = s.id) as bottle_count,
       exists (select 1 from wishlist_item w where w.shade_id = s.id) as wishlisted
from shade s;
```

### 4.3 `003_identifiers.sql` and `004_wheels_stacks.sql` (stages 5 and 6)

```sql
-- 003_identifiers.sql: learned codes. SKUs are not here: shade.sku already holds them.

create table shade_identifier (
  id           integer primary key,
  kind         text not null check (kind in ('gtin', 'printed')),
  value        text not null,                                 -- gtin: 13 digits; printed: "P259"
  shade_id     integer not null references shade (id) on delete cascade,
  source       text not null default 'learned',               -- v1 writes only 'learned'
  use_count    integer not null default 0,
  created_at   text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  last_used_at text,
  unique (kind, value)
);
create index shade_identifier_shade on shade_identifier (shade_id);
```

```sql
-- 004_wheels_stacks.sql

create table wheel (
  id         integer primary key,
  slug       text not null unique,                            -- 6 chars, the NFC/QR URL: /w/<slug>
  name       text not null,
  slot_count integer not null default 20 check (slot_count between 1 and 40),
  archived   integer not null default 0 check (archived in (0, 1)),
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- A stack is an ordered list of layers, owned by exactly one holder (a wheel slot in v1, a mani
-- in v3). Holders never share a stack row; "copy" duplicates the layer rows.
create table stack (
  id         integer primary key,
  name       text,                                            -- optional favourite name
  status     text not null default 'draft' check (status in ('draft', 'saved')),
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

create table stack_layer (
  id       integer primary key,
  stack_id integer not null references stack (id) on delete cascade,
  ord      integer not null check (ord >= 1),                 -- 1 = painted first (base)
  shade_id integer not null references shade (id),
  coats    integer not null default 1 check (coats between 1 and 5),
  unique (stack_id, ord)
);
create index stack_layer_shade on stack_layer (shade_id);     -- "where did I use topper X"

-- A slot row exists once it holds a swatch, a draft or a note; empty slots have no row.
-- stack_id is the saved swatch; draft_stack_id is the working copy while the builder is open
-- (a copy of the saved layers, or empty). Save swaps the draft in and deletes the old stack.
create table wheel_slot (
  wheel_id       integer not null references wheel (id) on delete cascade,
  position       integer not null check (position >= 1),      -- <= wheel.slot_count, checked in code
  stack_id       integer references stack (id) on delete set null,
  draft_stack_id integer references stack (id) on delete set null,
  painted_on     text,
  note           text,
  primary key (wheel_id, position)
) without rowid;
create unique index wheel_slot_stack on wheel_slot (stack_id) where stack_id is not null;
create unique index wheel_slot_draft on wheel_slot (draft_stack_id) where draft_stack_id is not null;
```

"Where did I use topper X" (shade detail page and the `?hl=` highlight on the wheel page):

```sql
select w.slug, w.name, ws.position, ws.stack_id
from stack_layer sl
join wheel_slot ws on ws.stack_id = sl.stack_id        -- saved stacks only, never drafts
join wheel w on w.id = ws.wheel_id and w.archived = 0
where sl.shade_id = :shade_id
group by ws.wheel_id, ws.position
order by w.name, ws.position;
```

### 4.4 Later tables (sketch only, not created in v1)

```
v2  shade_colour(shade_id, source catalog|wheel, L, a, b, palette_json, image_url, computed_at)
    shade_image_override(shade_id, image_url)        -- manual choice of the colour source image
    shade_observation(shade_id, seen_at, price_cents, compare_at_cents, available)
                                                     -- appended by sync only when the tuple changes
    event(id, kind, shade_id, payload, created_at, notified_at)   -- "what's new" feed + alert queue
    share_link(token, kind, created_at, revoked_at)  -- /share/<128-bit token>, revocable
v3  mani(id, worn_on, removed_on, stack_id, draft_stack_id, photo_path, note)
                                                     -- photos under /data/photos, resized on upload
```

Until `shade_observation` exists, price, availability and sale state are the latest values on
`shade`; there is no history, which is acceptable because nothing in v1 reads history.

## 5. Catalog sync

### 5.1 When and how

- An asyncio task started in the app lifespan (a CronJob would be a second workload). It runs
  daily at `POLISHED_SYNC_HOUR` (06:00) local time plus a random 0 to 30 minutes of jitter.
- **Catch-up:** 60 s after start, if there is no `ok` run in the last 30 hours (or none at all),
  run once with `trigger='catchup'`. The pod can restart or be rescheduled; a day is never lost.
- **Manual:** `POST /sync/run`, refused while a run is in progress and for
  `POLISHED_SYNC_MANUAL_COOLDOWN_S` (3600) after the last run started.
- **Single flight:** an `asyncio.Lock` plus the `running` row. At startup any `running` row older
  than one hour is closed as `error: interrupted`.
- **No scale-to-zero.** The home-ops `zeroscaler` components would stop the pod and the task
  with it; polished runs with one always-on replica and requests ~64 MB.
- **Request budget: 3 requests a day** (`GET /products.json?limit=250&page=N`, N = 1..3; stop at
  the first page with fewer than 250 products, hard cap 10 pages), never closer than
  `POLISHED_SYNC_MIN_INTERVAL_S` ≥ 1.0 s apart, User-Agent
  `polished/<version> (+https://github.com/janpuc/polished)`. HTTP 429 or 5xx on any page aborts
  the run (status `error`, nothing applied); the next attempt is the next scheduled run, with at
  most one retry an hour later on a 5xx. A 429 is never retried the same day. Redirects are not
  followed off `holotaco.com`.
- **No per-product `.json` fetches** (section 7 explains why). A first sync is 3 requests, not 372.

### 5.2 Algorithm

All pages are fetched into memory first (about 2.7 MB), then applied in **one transaction**, so a
failed page leaves the database untouched.

1. **Classify** every feed product, first match wins (`catalog/classify.py`):
   1. `handle` (NFC-normalised) is in `MANUAL_ALIASES` → `alias`, source `manual`. Applies to
      any product type, so a relisted shade can be pointed at its canonical row.
   2. `product_type == "Birthday Gift"` → `alias`, target handle = `handle` minus
      `-birthday-gift`. This test comes before the bundle test because gifts carry bundle tags.
   3. `product_type` not in `{"Nail Polish", "Top Coat", "Base Coat"}` → `skipped`.
   4. any tag contains `bundle` → `bundle`.
   5. otherwise → `shade`, kind `polish`, `topcoat` or `basecoat` from the type.

   Today: 372 shades, 46 bundles, 71 aliases, 37 skipped.
   `MANUAL_ALIASES = {"linear-holo-taco\u2122-birthday-gift": "linear-holo-taco",
   "royal-tea-blue-birthday-gift": "royal-tea-blue-2021"}`. (`aurora-unicorn-skin-birthday-gift`
   merges by handle because the target pool is all 372 shades, Top Coats included.)
2. **Hash** each product: sha256 over canonical JSON (sorted keys) of `title`, `handle`,
   `product_type`, sorted `tags`, `variants[0].sku`, `variants[0].id`, `variants[0].price`,
   `variants[0].compare_at_price`, `variants[0].available`, `published_at`, and the ordered image
   `src` values (which embed `?v=<timestamp>`). `updated_at` and `body_html` are excluded.
3. **Upsert `product`** by `shopify_product_id`: new row, or update when the hash differs
   (rewriting `raw_json` without `body_html`, `handle`, price, availability and `role`).
   Unchanged rows only get `last_seen`, `absent_syncs = 0`, `missing_since = null`; a row that
   was missing and is listed again counts as `returned`. A product with more than one variant
   uses `variants[0]` and logs a warning.
4. **Derive shades** for `role = shade` products that are new or changed: upsert `shade` by
   `product_id` (copy title, handle, sku, hero image = image with `position` 1, price cents from
   the decimal string, `compare_at` null when absent or `0`, `available`, `published_at`);
   recompute `search_text` (title, handle words, tag values; lowercase, accent-folded);
   replace the `shade_tag` rows from the `finish:`, `color:`, `collection:` tags; set
   `retired`, `retiring`, `is_topper` (kind `topcoat`, or kind `polish` and tag `color:clear`:
   known false positives `sticky-base` and `pink-smoothing-base`, harmless in a layer picker).
5. **Resolve aliases** for `role = alias` products with no `shade_alias` row: target handle
   (stripped suffix, or the manual map) looked up among `shade.handle`. Found → insert the
   alias row. Not found → leave unresolved, counted in `unresolved_aliases`, retried next sync.
   Resolved aliases are never re-evaluated, so later renames cannot break them.
6. **Absence accounting**, only when the feed is trustworthy: all pages fetched, and the feed
   holds at least 70% of the products seen by the last successful run. For every product not in
   this feed, `absent_syncs += 1`; at 3, `missing_since = today`. Rows are never deleted, and
   neither are shades, whatever their state.
7. **Close** the `sync_run` row with the counts.

The first sync into an empty database is a bulk import (everything is "new"); it records no
events. Re-running the same feed changes nothing (`changed_shades = 0`), which is a test.

### 5.3 Shade state rules

Stored: `available`, `retired`, `retiring`, `missing_since` (on the product). Derived in
`shades.status(shade)`, first match wins:

| Status | Condition | Label | Buyable |
|---|---|---|---|
| `missing` | product `missing_since` set | Not listed | no |
| `retired` | `retired` | Retired (or "Retired, last stock" when `available`) | only if `available` |
| `sold_out` | not `available` | Sold out (plus "retiring" when `retiring`) | no |
| `retiring` | `retiring` | Retiring soon | yes |
| `available` | otherwise | In stock | yes |

Sale is `price_cents < compare_at_cents` (strict). Manual shades have no status and no price.

### 5.4 Sync command and fixtures

`python -m polished sync` fetches live. `python -m polished sync --from-files p1.json p2.json
p3.json` applies local JSON pages with the same code path and no network, so local runs and
agents never touch the shop. Tests feed trimmed fixtures through `httpx.MockTransport`.

`tests/fixtures/feed_trimmed.json` is generated once by `scripts/make_fixtures.py` from the
snapshot (kept out of git) and committed: about 14 products, catalog fields only (title,
handle, type, tags, SKU, price, availability, two image URLs, no `body_html`), covering a normal
`HL-*-NP` polish, an older `HLT-NP-*` polish, a Top Coat topper with its birthday-gift copy, a
Base Coat, a bundle, a gift that merges by handle, a gift that needs the manual alias, a
retired shade, a soon-retiring one, a sold-out one, and an accessory. No single shade is on sale
in the real feed today, so the on-sale shade is a real shade whose `compare_at_price` the script
raises; the fixture README says so.

## 6. Searching and browsing

- `search_text` is lowercase, accent-folded (`NFKD`, marks stripped), punctuation to spaces.
  A query is tokenised the same way; every token must match as `LIKE '%token%'`. 372 rows: no
  FTS5.
- Ranking in the picker and the home search: owned first, then wishlisted, then the rest; within
  a group, titles starting with the query first, then alphabetical. Limit 30.
- Filters on `/shades`: `finish` and `color` (multi-select, any-of within a namespace),
  `collection` (one), `kind`, `status` (`any|buyable|retired|sold_out`), `owned`
  (`any|owned|not_owned|wishlist`), `sort` (`name|newest|price`; newest = `published_at`),
  `page` (40 a page, a "Load more" button, not infinite scroll).
- Images are hotlinked from `cdn.shopify.com` with `&width=` added for thumbnails (Shopify's
  image CDN resizes by query parameter) and `loading="lazy"`. The service worker does not cache
  cross-origin images.

## 7. Identifier lookup

**Catalog barcodes are not used.** The Spirit Fingers bottle in hand reads `810170284120`; the
catalog says `810065564276`, and `810170284120` appears nowhere in the 488 fetched products.
Of the catalog's barcodes, 126 are nine-digit values that cannot be GTINs and one valid value is
shared by two products. So v1 does not fetch per-product JSON and does not seed
`shade_identifier` from the catalog, not even as a "low-confidence suggestion": a wrong
suggestion costs a tap and teaches the main user to distrust the screen, and the data would cost 372
requests plus a code path that can never be confirmed. If a later scan shows the catalog value on
a real bottle, adding it is a small v2 change (the `source` column exists for it).

**Learned mappings are the primary path.** Scan once, pick the shade once, and it is remembered.

### 7.1 Normalisation (`gtin.py`)

`normalise_gtin(raw) -> str | None`: strip whitespace; digits only; length 8, 12, 13 or 14;
the GS1 check digit (weights 3, 1 alternating from the right) must pass; a 14-digit value is
accepted only with a leading `0` (otherwise it is a case or ITF-14 code, not a bottle); the
result is left-padded with zeros to 13 digits. So `810170284120` and `0810170284120` (ZXing
reports a UPC-A either way) both become `0810170284120`, and `795203598` is rejected. An invalid
scan is "couldn't read that reliably, try again" and is never learned.

`normalise_printed(raw) -> str | None`: strip, uppercase, remove spaces; all digits gets the
prefix `P`; the result must match `^[A-Z]{1,2}\d{1,5}$`.

### 7.2 Resolution order (`identifiers.resolve(conn, q, via)`)

Input is the scanner's decoded text or whatever was typed into the search field.

1. `normalise_gtin(q)` succeeds → look up `shade_identifier(kind='gtin')`.
   - **Found:** result `match`: the shade card, with "Add bottle" and "This isn't it"
     (deletes the mapping). Increments `use_count`. The page never adds a bottle on its own.
   - **Not found:** result `unknown_code`: "New barcode. Which shade is this?" with the
     picker (`/search?ctx=learn`). Choosing a shade `POST /identifiers` → saved, then the
     add-bottle form opens.
2. `q` looks like a number but fails the GTIN check (8 to 14 digits) → result `invalid_code`.
3. `normalise_printed(q)` succeeds (`259`, `p259`) → look up `shade_identifier(kind='printed')`.
   - **Found:** result `suggestion`: "P259 was Spirit Fingers on a bottle you added before"
     with a confirm button and, underneath, ordinary name search results. A P code is a
     suggestion, never an auto-match, because it is unknown whether P numbers are per shade or
     per batch (BRIEF open question 1).
   - **Not found:** result `unknown_printed`: pick the shade; the P code is attached to the
     bottle being added and learned when the bottle is saved.
4. `q` equals a `shade.sku` (case-insensitive, `HL-00169-NP`) → result `match` (a catalog fact).
5. Otherwise → ordinary name search (section 6) as `results`.

**Learning:** `POST /identifiers` stores a gtin mapping. Saving a bottle with a P code stores
`printed → shade` if absent. If the code already points at a different shade the old mapping is
kept, the bottle is saved with the code, and the form shows "P259 was Spirit Fingers before"; the
`/identifiers` page lists every learned mapping and deletes wrong ones. Learned mappings are the
only rows in `shade_identifier`, so "learned wins" holds by construction.

Typing `259` into the global search runs the same resolver, so the scan-free path costs
nothing.

### 7.3 Scanner island (`static/js/scanner.js`)

- `getUserMedia({video: {facingMode: {ideal: 'environment'}, width: {ideal: 1280}}, audio:
  false})` into a `<video playsinline muted>`; the stream stops as soon as a code is accepted
  and when the page hides.
- Decode with vendored `zxing-wasm` (reader build, `prepareZXingModule` with a `locateFile`
  override pointing at `/static/vendor/zxing-wasm/zxing_reader.wasm`), formats `EAN-13`,
  `UPC-A`, `EAN-8`, `tryHarder` on, centre-cropped frames at about 6 per second. A code is
  accepted after two identical consecutive reads. `BarcodeDetector` is feature-detected as a
  two-line branch and not tested (iPhone only).
- Fallback button "Take a photo of the barcode": `<input type="file" accept="image/*"
  capture="environment">`, decoded from the still, which is sharper than video frames for a
  small printed barcode.
- On accept it calls `htmx.ajax('GET', '/lookup/resolve?q=<digits>&via=scan', '#lookup-result')`.
- CSP: `script-src 'self' 'wasm-unsafe-eval'`.

## 8. Authentication

Pocket ID OIDC with authlib, exposed on `envoy-external`; `AUTH_MODE=oidc` by default.

### 8.1 Flow

```
GET  /auth/login?next=/w/k3m9xq
       validate next (starts with "/", not "//", no scheme) → session["login_next"]
       authlib authorize_redirect: scope "openid profile email groups", PKCE S256, state, nonce
       → 302 https://id.janpuc.com/authorize?…redirect_uri=<PUBLIC_URL>/auth/callback
GET  /auth/callback?code&state
       authorize_access_token: checks state, exchanges the code (PKCE verifier + client secret),
       validates the id_token (signature via JWKS, iss, aud, exp, nonce)
       claims = id_token claims; if "groups" is absent there, call the userinfo endpoint
       groups ∩ POLISHED_OIDC_ALLOWED_GROUPS (exact match; default ID-Users, ID-Admin) empty → 403
       page "This account isn't allowed here", no session is created
       otherwise session.clear(); session = {sub, name, iat, seen}; → 302 login_next or /
POST /auth/logout
       session.clear() → 302 /auth/signed-out (public page with a "Sign in again" link;
       no auto-redirect, or Pocket ID's remember-me would sign her straight back in and look
       like a failed logout). Local logout only; Pocket ID's own session stays.
```

### 8.2 Session

- Starlette `SessionMiddleware` (signed with `POLISHED_SESSION_SECRET`, itsdangerous) carries both
  authlib's short-lived state and the login. Cookie `polished_session`: `HttpOnly`,
  `Secure` (oidc mode), **`SameSite=Lax`** (Strict would drop it on the return from Pocket ID
  and break the state check), path `/`, `Max-Age` 30 days (`POLISHED_SESSION_DAYS`).
- **Rolling:** when `seen` is older than 1 day the gate rewrites it, which re-issues the cookie.
  **Absolute cap:** `iat` older than `POLISHED_SESSION_MAX_DAYS` (90) forces a new login, which
  also re-checks the groups.
- **iOS:** a tag tap or QR scan opens Safari, the installed PWA has its own cookie jar, so the main user
  signs in once in each. The long session plus Pocket ID's remember-me keep that rare.
- Revoking everyone: rotate `POLISHED_SESSION_SECRET` (the ExternalSecret item) and restart.

### 8.3 Gate and CSRF

Middleware order (outermost first): security headers → Origin check → `SessionMiddleware` →
auth gate → routes.

- **Deny by default.** The gate lets through only: `/healthz`, `/static/*`,
  `/manifest.webmanifest`, `/sw.js`, `/offline`, `/auth/login`, `/auth/callback`,
  `/auth/logout`, `/auth/signed-out`. (`/share/*` joins in v2.) Everything else needs a valid
  session. The manifest, service worker and icons are public because browsers fetch them
  without credentials.
- Unauthenticated: a GET navigation gets `302 /auth/login?next=<path>`; an HTMX request gets
  `401` with `HX-Redirect: /auth/login?next=<current path>`; any other method gets `401`
  (never a redirect that could replay a POST). Unknown paths and unknown slugs answer exactly
  like known ones until the gate passes, so nothing leaks.
- **Origin check:** for POST/PUT/PATCH/DELETE the `Origin` header (else `Referer`) host must
  equal the host of `POLISHED_PUBLIC_URL`; otherwise 403. Together with `SameSite=Lax` this is
  the CSRF defence; there are no tokens to thread through partials.
- **`AUTH_MODE=none`** (local dev and tests): the gate injects `sub="dev"`. At startup it is
  refused unless the host of `POLISHED_PUBLIC_URL` is `localhost` or `127.0.0.1`, so the cluster
  manifest can never run open by accident, and it logs a warning on every start.
- Other headers: `Content-Security-Policy: default-src 'self'; img-src 'self' https://cdn.shopify.com
  data:; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; worker-src
  'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: same-origin`. Login is a plain link and
  logout a same-origin form, so `form-action 'self'` does not block the OIDC redirect.

## 9. Swatch wheels, NFC and QR

- A wheel has a name, `slot_count` (default 20) and a **slug**: 6 characters from the lowercase
  Crockford base32 alphabet (`0-9a-z` without `i l o u`), drawn with `secrets`, retried on a
  unique violation. URL: `https://polished.janpuc.com/w/<slug>`, short enough for any NFC tag.
- **The tag points at the wheel, not at its slots**, and not at the name or the integer id:
  rearranging is a database edit, renaming never invalidates a tag.
- **Wheel page `/w/<slug>`** (the canonical page; `/wheels` links to it): a 4-column grid of
  slots 1..20. A filled slot shows its position, the stack summary and thumbnails; an empty slot
  shows "+"; a slot with an open draft shows a "draft" dot. Tapping a tile opens the stack
  builder (section 10). `?hl=<shade_id>` highlights every slot whose stack contains that shade
  and scrolls to the first (`#slot-12`), which is what "Swatched on" links on the shade page use.
- **Tag page `/wheels/<id>/tag`:** the full URL with a Copy button, the QR code, and the NFC
  Tools steps (Write → Add a record → URL/URI → paste → Write; Web NFC writing does not exist
  on iPhone). Shown right after a wheel is created.
- **QR:** `GET /wheels/<id>/qr.svg`, generated on the fly by `segno` (`error='m'`, scale 8,
  border 2, no XML declaration), `image/svg+xml`, `Cache-Control: private, max-age=86400`. The
  QR carries the same URL as the tag, so a failed tag, a laptop or a printed sticker all work;
  the iOS camera opens it natively.
- **Moving a tag:** "New tag URL" regenerates the slug (the old tag then 404s once logged in);
  "Take the tag of…" on wheel B swaps slugs with wheel A, so a tag stuck on a discarded wheel can
  point at its replacement without rewriting it. Wheels are archived, never deleted; an archived
  wheel's page shows a banner with Restore and the take-tag action.
- **Tapping a tag while logged out** (Safari has no session): `GET /w/k3m9xq` →
  `302 /auth/login?next=%2Fw%2Fk3m9xq` → Pocket ID (passkey / Face ID, one step with
  remember-me) → `/auth/callback` → `302 /w/k3m9xq`. A logged-in Safari goes straight to the
  wheel. The wheel's existence is not revealed before login. If the PWA is installed, the tap
  still opens Safari (iOS does not route tag URLs to home-screen apps).

## 10. Layer-stack builder

**Model:** painting order. A stack lists layers in the order they were painted, labelled Base,
2nd, 3rd, ..., Top (a one-layer stack has no label; two layers are Base and Top). It is rendered
everywhere as `One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco`: names left to right as in
Jan's "x + y + z", `×N` only when N is greater than 1. Each layer chip shows the shade's hero
thumbnail (a colour dot from `shade_colour` joins in v2). Maximum 8 layers, 1 to 5 coats each,
the same shade may appear twice, any shade over any shade.

**Default coats** (`stacks.default_coats(shade)`): 1 for `topcoat`, `basecoat` or `is_topper`
shades, 2 for other polish. "Over black" inserts One-Coat Black with 1 coat.

**Draft lifecycle.** Every edit is a server round trip against a draft `stack` row; the client
keeps nothing, so a dropped connection or a backgrounded tab loses nothing.

1. **Open.** On the wheel page, tapping slot 12 posts `POST /wheels/{id}/slots/12/draft`
   (`hx-target="#sheet-body"`). The server creates the `wheel_slot` row if missing, then returns
   the existing `draft_stack_id` if there is one ("Resumed your draft" note), else creates a
   draft `stack` containing a copy of the slot's saved layers (or none) and stores it in
   `draft_stack_id`. The partial is the sheet; `sheet.js` calls `showModal()` on the `<dialog>`
   when `#sheet-body` is swapped.
2. **Sheet layout, top to bottom** (bottom-anchored `<dialog>`, `max-height: 100dvh`; the
   layers list and the results scroll independently; buttons are at least 44 pt). Layers are
   listed in painting order, **Base at the top**, as the advice recommends:

   ```
   Wheel "Holos" · slot 12                                    [Cancel]
   One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco      <- live summary
   Base  [img] One-Coat Black       −  1  +   ↑ ↓  ×
   2nd   [img] Spirit Fingers       −  2  +   ↑ ↓  ×
   Top   [img] Flakie Holo Taco     −  1  +   ↑ ↓  ×
   [ Over black ]  [ Copy from… ]  [ Same as last ]
   [ search shades, or a P code        ] [scan]
   (Owned) (Toppers) (All)
   results: owned first, then wishlist, then catalog ...
   Name (optional) [        ]   Note [        ]
   [ Save ]
   ```

3. **Append (x + y + z).** Tap a result: `POST /stacks/{id}/layers` with `shade_id`
   (`hx-target="#stack-layers"`, `hx-swap="outerHTML"`) appends at `ord = max + 1` with the
   default coats and keeps the sheet and the search field open, so three layers are three taps
   plus typing. The response re-renders the layers list and the summary (an out-of-band swap) and
   resets the results to the empty query (owned shades first). `sheet.js` refocuses the field on
   `htmx:afterSwap`; on iOS the keyboard may close after a tap (focus outside a user gesture),
   which costs one extra tap and is checked on the real phone in stage 7.
4. **Search field** accepts a name, a P code (`259`) or the scan button: `GET /search?ctx=stack
   &stack_id=…&q=…&filter=owned|toppers|all`, debounced 200 ms. P-code input uses the resolver
   of section 7 and shows a `suggestion` row first.
5. **Coats:** `−` / `+` post `delta=-1|+1`, clamped to 1..5 (`−` is disabled at 1; removal is
   `×`). **Reorder:** `↑` / `↓` post `dir=up|down`; the first row has no `↑`, the last no `↓`;
   the swap goes through `ord = 0` as a temporary value because `(stack_id, ord)` is unique. No
   drag and drop: it fights mobile Safari and HTMX, and with two to four layers arrows are
   faster. **Remove:** `×` deletes the layer and renumbers `ord` 1..n; no confirmation (re-adding
   is one tap).
6. **Templates.**
   - **Over black:** `POST /stacks/{id}/template/over-black` inserts the shade with handle
     `POLISHED_OVER_BLACK_HANDLE` (default `one-coat-black`) at `ord = 1`, shifting the rest up,
     unless the first layer already is that shade ("Already over black"). The button is hidden
     when that handle is not in the catalog. Toppers are mostly swatched over black, so add the
     topper, tap Over black, done.
   - **Copy from…:** `GET /stacks/{id}/copy-sources?q=` replaces the results area with saved
     stacks (wheel name, slot, summary, most recently saved first, searchable by shade name);
     `POST /stacks/{id}/template/copy` with `source_stack_id` replaces the draft's layers with
     copies of that stack's rows (`hx-confirm` when the draft already has layers). Copies the
     rows, never the stack, so editing one slot never touches another.
   - **Same as last:** the same route with `source=last`: the most recently saved stack.
7. **Save:** the name, note and painted-on date live in a form that the layer operations never
   re-render (they swap only `#stack-layers`), so typed text survives. `POST /stacks/{id}/save`:
   requires at least one layer (otherwise a 422 inline message); in one transaction it deletes
   the slot's previous saved stack (layers cascade), points `stack_id` at the draft, clears
   `draft_stack_id`, sets the stack `saved`, stores the name, the slot note, and `painted_on`
   (default today). The response swaps the slot tile out of band (`#slot-12`) and sends
   `HX-Trigger: sheetClose`.
8. **Cancel:** `POST /stacks/{id}/cancel` deletes the draft stack, clears `draft_stack_id`, and
   removes the slot row if it holds no saved stack and no note. Dismissing the sheet any other
   way (backdrop, tab switch, app switch) keeps the draft; the tile shows the "draft" dot and
   the next tap resumes it.
9. **Clear a swatch:** a saved slot's sheet has "Remove swatch": `POST
   /wheels/{id}/slots/{pos}/clear` (`hx-confirm`) deletes the saved stack, any draft and the slot
   row.

Operations on a stack id are refused (409) unless the stack is a draft that some slot points at.

## 11. PWA

- `GET /manifest.webmanifest` (`application/manifest+json`): `name` "Polished", `short_name` "Polished", `start_url`
  `/?source=pwa`, `scope` `/`, `display` `standalone`, background and theme colours, icons
  192 and 512 (plus a maskable 512). `<link rel="apple-touch-icon">` (180 px PNG) and the
  `apple-mobile-web-app-*` meta tags are in `base.html` because iOS ignores the manifest icons.
  Icons are committed PNGs generated once by `scripts/make_icons.py`.
- `GET /sw.js` is served from the root so its scope is `/`, with `Cache-Control: no-cache`. It
  has three jobs: precache `/offline`, `app.css`, `htmx.min.js` and the icons into
  `polished-static-<version>`; serve `/static/*` cache-first (templates append `?v=<version>`,
  so a release changes the URLs); answer a failed navigation with `/offline`. It never caches
  HTML, partials, API responses or cross-origin requests, never touches non-GET requests, and
  deletes old caches on `activate`. No offline writes, no background sync.
- `/offline` is a static page ("Polished needs a connection") and is public.
- The zxing-wasm file (about a megabyte) is cached by the service worker on first scan, not
  precached.

## 12. Configuration

All environment variables, prefix `POLISHED_`. Secrets come only from the environment.

| Variable | Default | Meaning |
|---|---|---|
| `DB_PATH` | `/data/polished.db` | SQLite file |
| `PUBLIC_URL` | none, required | External base URL (`https://polished.janpuc.com`): OIDC redirect, QR/tag URLs, Origin check |
| `AUTH_MODE` | `oidc` | `oidc` or `none` (dev only, localhost `PUBLIC_URL` only) |
| `OIDC_ISSUER` | `https://id.janpuc.com` | Discovery at `<issuer>/.well-known/openid-configuration` |
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | none | From the operator-written Secret; the secret is a `SecretStr` |
| `OIDC_ALLOWED_GROUPS` | `ID-Users,ID-Admin` | Comma-separated, exact match against the token's `groups` claim |
| `SESSION_SECRET` | none, ≥ 32 chars | Signs the session cookie; required in `oidc` mode, `none` mode makes a random one per start (section 14, item 10) |
| `SESSION_DAYS`, `SESSION_MAX_DAYS` | `30`, `90` | Rolling and absolute session lifetime |
| `HOST`, `PORT` | `0.0.0.0`, `8080` | Listener |
| `STORE_URL` | `https://holotaco.com` | Shop base for the feed and cart permalinks |
| `SYNC_ENABLED` | `true` | Scheduler on/off (the manual button and CLI still work) |
| `SYNC_HOUR`, `SYNC_JITTER_MIN` | `6`, `30` | Daily run, local time |
| `SYNC_MIN_INTERVAL_S` | `1.0` | Gap between requests; values below 1.0 are rejected at startup |
| `SYNC_MANUAL_COOLDOWN_S` | `3600` | Minimum time between runs started by the button |
| `TIMEZONE` | `Europe/Warsaw` | Household timezone |
| `OVER_BLACK_HANDLE` | `one-coat-black` | Shade the "Over black" template inserts |
| `LOG_LEVEL`, `VERSION` | `INFO`, `dev` | Logging; the image build sets `VERSION` |

Later: `MATRIX_WEBHOOK_URL` (v2 notifier), `PHOTO_DIR` (v3), `LITELLM_URL` (v2 vision).
`.env.example` documents the dev subset with dummy values.

## 13. Routes (v1)

"Auth" is yes for everything except the public rows. `P` = partial returned when
`HX-Request` is set (section 3.2). All mutations are POST. "Stage" is the PLAN.md stage that
builds it.

### 13.1 Public

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/healthz` | `{status, version, schema}`; checks the DB opens | JSON | 1 |
| GET | `/manifest.webmanifest` | PWA manifest | JSON | 3 |
| GET | `/sw.js` | Service worker, root scope | JS | 3 |
| GET | `/offline` | Offline fallback page | full page | 3 |
| GET | `/static/{path}` | CSS, JS, vendored libs, icons | file | 1 |
| GET | `/auth/login` | Start OIDC (`?next=`) | 302 | 1 |
| GET | `/auth/callback` | Finish OIDC, group check, create session | 302 / 403 page | 1 |
| POST | `/auth/logout` | Clear session | 302 | 1 |
| GET | `/auth/signed-out` | "Signed out" + sign-in link | full page | 1 |

### 13.2 Home, search, browse

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/` | Home: search field and links; stage 4 adds counts and recent bottles, stage 5 the Scan button | full page | 3 |
| GET | `/search` | Typeahead rows. Params `q`, `ctx` (`home`, `stack`, `learn`), `filter` (`owned/toppers/all`), `stack_id`, `kind`+`value` for `learn`. Row action depends on `ctx`; `home` in stage 3, `learn` in 5, `stack` in 7 | partial | 3 |
| GET | `/shades` | Browse list with filters (section 6) | full page; P = rows + Load more | 3 |
| GET | `/shades/{id}` | Detail: images, tags, price/status, product link; stage 4 adds bottles and wishlist, stage 6 "Swatched on" | full page | 3 |
| GET | `/shades/new` | Manual shade form (gifted non-catalog bottle) | full page / P | 4 |
| POST | `/shades` | Create manual shade (title, kind) | 302 to the shade | 4 |
| GET | `/sync` | Last runs, counts, Sync now | full page | 2 |
| POST | `/sync/run` | Start a manual run (409 running, 429 cooldown) | P status | 2 |
| GET | `/sync/status` | Status box; polls every 2 s while running | P | 2 |

### 13.3 Bottles and wishlist

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/bottles` | My bottles grouped by shade; filters `state`, `archived` | full page / P | 4 |
| GET | `/shades/{id}/bottles/new` | Add-bottle form (P code field, state, date, price, notes) | P (sheet) | 4 |
| POST | `/shades/{id}/bottles` | Create; learns the P code (stage 5) | P `#bottles`, `HX-Trigger: sheetClose` | 4 |
| GET | `/bottles/{id}/edit` | Edit form | P (sheet) | 4 |
| POST | `/bottles/{id}` | Update | P `#bottles` | 4 |
| POST | `/bottles/{id}/state` | Set full / half / low / empty | P bottle card | 4 |
| POST | `/bottles/{id}/archive` | `archived=0/1` | P | 4 |
| POST | `/bottles/{id}/delete` | Hard delete a mistaken entry (`hx-confirm`) | P | 4 |
| GET | `/wishlist` | Items by priority, total (all, and buyable), cart box | full page | 4 |
| POST | `/shades/{id}/wishlist` | Add (priority 2) | P button | 4 |
| POST | `/wishlist/{id}` | Priority (1 to 3) and note | P row | 4 |
| POST | `/wishlist/{id}/delete` | Remove | P | 4 |
| GET | `/wishlist/cart` | Permalink for buyable items up to `max_priority` | P cart box | 4 |

Cart permalink: `https://holotaco.com/cart/<variant_id>:1,<variant_id>:1,…`, buyable items only
(`available` and not missing), quantity 1, opened with `target="_blank" rel="noopener"`. Not yet
tested against this store; stage 4 ends with a manual check by Jan, and the box also offers
"Copy the list" as a fallback.

### 13.4 Identifier lookup

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/lookup` | Scan button, text field, result area | full page | 5 |
| GET | `/lookup/resolve` | `q`, `via=scan/typed` → `match`, `suggestion`, `unknown_code`, `unknown_printed`, `invalid_code`, `results` (section 7.2) | partial | 5 |
| POST | `/identifiers` | Learn `kind`, `value`, `shade_id` | P "Saved" + add-bottle form | 5 |
| GET | `/identifiers` | Learned mappings | full page | 5 |
| POST | `/identifiers/{id}/delete` | Delete a mapping | P | 5 |

### 13.5 Wheels and stacks

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/wheels` | Wheels (archived behind a toggle), new-wheel form | full page | 6 |
| POST | `/wheels` | Create (name, slot_count default 20) | 302 `/wheels/{id}/tag` | 6 |
| GET | `/w/{slug}` | The wheel page; NFC and QR target; `?hl=<shade_id>` | full page | 6 |
| POST | `/wheels/{id}` | Rename | P header | 6 |
| POST | `/wheels/{id}/archive` | `archived=0/1` | 302 | 6 |
| GET | `/wheels/{id}/tag` | URL, Copy, QR, NFC Tools steps | full page | 6 |
| GET | `/wheels/{id}/qr.svg` | QR code | `image/svg+xml` | 6 |
| POST | `/wheels/{id}/slug/regenerate` | New slug | 302 tag page | 6 |
| POST | `/wheels/{id}/slug/take` | Swap slugs with `from_wheel_id` | 302 tag page | 6 |
| POST | `/wheels/{id}/slots/{pos}/draft` | Open or resume the builder | P sheet | 7 |
| POST | `/wheels/{id}/slots/{pos}/clear` | Remove swatch (stack, draft, row) | P tile | 7 |
| GET | `/stacks/{id}/sheet` | Re-render a draft's sheet | P | 7 |
| POST | `/stacks/{id}/layers` | Append `shade_id` | P `#stack-layers` | 7 |
| POST | `/stacks/{id}/layers/{lid}/move` | `dir=up/down` | P | 7 |
| POST | `/stacks/{id}/layers/{lid}/coats` | `delta=-1/+1` | P | 7 |
| POST | `/stacks/{id}/layers/{lid}/delete` | Remove a layer | P | 7 |
| POST | `/stacks/{id}/template/over-black` | Insert the base | P | 7 |
| GET | `/stacks/{id}/copy-sources` | Saved stacks to copy from | P | 7 |
| POST | `/stacks/{id}/template/copy` | `source_stack_id` or `source=last` | P | 7 |
| POST | `/stacks/{id}/save` | Commit draft to its slot | P tile (OOB) + `sheetClose` | 7 |
| POST | `/stacks/{id}/cancel` | Discard the draft | P + `sheetClose` | 7 |

## 14. Deviations from the advice and from the decisions so far

1. **No catalog barcode seeding and no per-product `.json` fetch** (section 7). The advice and
   the earlier decision 5 seeded `gtin` rows from catalog barcodes; the bottle in hand disproves
   them. Sync is 3 requests a day. `shade_identifier.source` stays for a v2 change if evidence
   turns up.
2. **`sku` is not an identifier kind.** `shade.sku` already is the catalog's, unique today but
   not guaranteed, so it is a plain indexed column and resolution step 4 reads it directly.
3. **Bundle test is "any tag containing `bundle`"**, not `bundle:product`: the latter finds 38,
   not 46. Gifts are classified before bundles.
4. **Birthday gifts: 69 merge by handle, 2 manual.** The advice listed three manual aliases
   because it matched against polish only; `aurora-unicorn-skin` merges automatically once Top
   Coats are in the target pool (68 + 1).
5. **The advice's "44 on sale" are all bundles; no single shade is on sale today.** Retired is
   118 and sold-out 48 over the 372 shades (the advice's 117 and 60 counted bundles too).
6. **Price and availability live on `shade`** (latest values) and `shade_observation` is v2, as
   advised, but the v1 sync does not write history.
7. **Stack drafts live on `wheel_slot.draft_stack_id`**, not a separate drafts table: a draft is
   a `stack` row with `status='draft'` that exactly one slot points at.
8. **v1 includes wheels and stacks** (the advice made them v2), per Jan: layers are "the best
   part of the system".
9. **No offline cache of HTML or cross-origin images**, and no Web NFC, per the advice.
10. **`SESSION_SECRET` is optional in `AUTH_MODE=none`** (stage 1): a random one is made per start,
    so the dev commands in `AGENTS.md` run without it. `oidc` mode still refuses to start without
    one of at least 32 characters, and also without `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET`.
11. **The HTMX 401 sends the user back to the page, not the partial.** `HX-Redirect` carries the
    path of the `HX-Current-URL` header when it names this host, else the requested path (section
    8.3 says "current path"); both go through the same `next` validation.
12. **The Origin check compares host and port** (`netloc`) of `Origin`/`Referer` with `PUBLIC_URL`,
    so `localhost:8080` and `localhost:9999` differ. Because the check runs before the gate
    (section 8.3), a signed-out `POST` without an `Origin` is 403 and with a good one 401.
13. **htmx is pinned to 2.0.11** (the 2.x line `htmx-config` in section 3.2 is written for; htmx 4
    exists on npm and is not used). Source and checksum are in `static/vendor/VERSIONS.txt`.

## 15. Home-ops manifests

Prepared as files under `deploy/home-ops/` in this repo (stage 8) for Jan to copy into
`kubernetes/apps/selfhosted/polished/`. They mirror serendip (custom image, init container,
Recreate, reloader) and mealie (Pocket ID client, `envoy-external`). Nothing is applied from
here, and home-ops is never edited.

| File | Key values |
|---|---|
| `selfhosted/polished/ks.yaml` | Flux `Kustomization` `polished`; components `../../../../components/kopiur/backup` only (**no zeroscaler**: the in-process sync needs the pod up); `dependsOn` `miroir-config` (miroir-system) and `pocket-id-instance` (security); `postBuild.substitute`: `APP: polished`, `KOPIUR_CAPACITY: 2Gi`, `KOPIUR_COPYMETHOD: Direct`; `targetNamespace: selfhosted`; `wait: false` |
| `selfhosted/polished/app/kustomization.yaml` | resources: externalsecret, helmrelease, ocirepository, pocketidoidcclient |
| `selfhosted/polished/app/ocirepository.yaml` | bjw-s `app-template` 5.2.1, as mealie and serendip |
| `selfhosted/polished/app/helmrelease.yaml` | controller `polished`, `strategy: Recreate`, `reloader.stakater.com/auto: "true"`; init container `migrate` (`python -m polished migrate`); container `app` image `ghcr.io/janpuc/polished:<tag>` (digest added on first release); env `POLISHED_DB_PATH=/data/polished.db`, `POLISHED_PUBLIC_URL=https://polished.janpuc.com`, `POLISHED_AUTH_MODE=oidc`, `POLISHED_OIDC_ISSUER=https://id.janpuc.com`, `POLISHED_OIDC_ALLOWED_GROUPS=ID-Users,ID-Admin`, `POLISHED_TIMEZONE=Europe/Warsaw`; `envFrom` secrets `polished-secret` and `polished-oidc-credentials`; probes `GET /healthz` on 8080; resources 10m / 64Mi request, 256Mi limit; `securityContext` `readOnlyRootFilesystem: true`, drop ALL, uid/gid/fsGroup 1000, `runAsNonRoot`; service port 8080; `route.app` hostname `polished.janpuc.com`, `parentRefs` `envoy-external` in `network`, Gatus annotation `conditions: ["[STATUS] == 200"]`, `path: /healthz`; persistence `data` `existingClaim: polished` at `/data`, `tmp` emptyDir at `/tmp` |
| `selfhosted/polished/app/externalsecret.yaml` | `ExternalSecret` `polished`, store `onepassword-connect`, target `polished-secret`, key `POLISHED_SESSION_SECRET` from field `SESSION_SECRET` of the 1Password item `polished` |
| `selfhosted/polished/app/pocketidoidcclient.yaml` | `PocketIDOIDCClient` `polished`; callback `https://polished.janpuc.com/auth/callback`; `pkceEnabled: true`; `allowedUserGroups` `id-users` and `id-admin` (namespace `security`); secret keys `POLISHED_OIDC_CLIENT_ID`, `POLISHED_OIDC_CLIENT_SECRET` (the operator writes `polished-oidc-credentials`) |
| `selfhosted/kustomization.yaml` | one line to add: `- ./polished/ks.yaml` after `medibrowserr` |

By hand, outside the repo and not by an agent: create the 1Password item `polished` with a random
`SESSION_SECRET` (`openssl rand -hex 32`); create the GitHub repo, enable Actions, add the
`OP_SERVICE_ACCOUNT_TOKEN` secret the Renovate workflow reads, and make the ghcr package public
(home-ops uses no image pull secrets); after the first release, put the tag and digest in the
HelmRelease. DNS needs nothing: the tunnel serves `*.janpuc.com` and `cloudflare-dns` follows the
HTTPRoute.

Known operational risk: kopiur `Direct` copies the live SQLite file (as serendip does). WAL
checkpoints make a torn copy unlikely but not impossible; if a restore ever fails, switch
`KOPIUR_COPYMETHOD` to `Snapshot`, or add a nightly `VACUUM INTO /data/backup/polished.db`.

## 16. Risks and open questions

- **Barcode scanning on iPhone:** zxing-wasm reading a small printed bottle barcode under phone
  lighting is unproven, which is why name search and P-code entry ship first and the still-photo
  fallback exists. Stage 5 ends with a check on the main user's or Jan's phone.
- **P codes:** per-shade or per-batch is unknown (one Spirit Fingers bottle). They stay a
  per-bottle field and a suggestion.
- **Safari versus PWA double login** and the keyboard behaviour of the bottom sheet are
  checked on the real phone (stages 3, 7).
- **Cart permalink** is untested against holotaco.com.
- **Group claim:** Pocket ID must emit `groups` for the `groups` scope; the callback falls back to
  the userinfo endpoint. First deploy confirms the claim shape.
- **Currency** is assumed USD.
- **BRIEF.md** names two people; whether first names stay in a public repo is Jan's call
  (the advice raised it). The app stores no names beyond the Pocket ID display name in a cookie.

## Appendix A. Reproducing the catalog numbers

`python3 -I facts.py research` with the script below (save it outside the repo, never next to
the JSON: `-I` stops Python importing from the current directory). It prints the totals in
section 2. The GTIN lines use `research/barcodes.json` and the check-digit rule of section 7.1.

```python
import collections as C, json, re, sys
P = [p for i in (1, 2, 3) for p in json.load(open(f"{sys.argv[1]}/p{i}.json"))["products"]]
v = lambda p: p["variants"][0]
bundle = lambda p: any("bundle" in t for t in p["tags"])
kind = {"Nail Polish": "polish", "Top Coat": "topcoat", "Base Coat": "basecoat"}
shades = [p for p in P if p["product_type"] in kind and not bundle(p)]
bundles = [p for p in P if p["product_type"] in kind and bundle(p)]
gifts = [p for p in P if p["product_type"] == "Birthday Gift"]
by_handle = {p["handle"] for p in shades}
print("products", len(P), "| shades", len(shades), dict(C.Counter(kind[p["product_type"]] for p in shades)),
      "| bundles", len(bundles), "| gifts", len(gifts), "| skipped", len(P) - len(shades) - len(bundles) - len(gifts))
print("gifts merging by handle", sum(p["handle"].removesuffix("-birthday-gift") in by_handle for p in gifts),
      "| manual:", [p["handle"] for p in gifts if p["handle"].removesuffix("-birthday-gift") not in by_handle])
tag = lambda p, t: t in p["tags"]
ret = [p for p in shades if tag(p, "collection:retirement")]
print("retired", len(ret), "unavailable", sum(not v(p)["available"] for p in ret),
      "| retiring", sum(tag(p, "collection:soon-retiring") for p in shades),
      "| sold out (unavailable, not retired)", sum(not v(p)["available"] and not tag(p, "collection:retirement") for p in shades),
      "| buyable", sum(v(p)["available"] for p in shades))
sale = lambda p: v(p)["compare_at_price"] and float(v(p)["price"]) < float(v(p)["compare_at_price"])
print("on sale: shades", sum(bool(sale(p)) for p in shades), "bundles", sum(bool(sale(p)) for p in bundles),
      "| shades with compare_at < price", sum(bool(v(p)["compare_at_price"]) and float(v(p)["price"]) > float(v(p)["compare_at_price"]) for p in shades))
print("SKU: HL-*-NP", sum(bool(re.fullmatch(r"HL-\d{5}-NP", v(p)["sku"])) for p in shades),
      "| polish HL-*-NP", sum(bool(re.fullmatch(r"HL-\d{5}-NP", v(p)["sku"])) for p in shades if p["product_type"] == "Nail Polish"),
      "| unique SKUs", len({v(p)["sku"] for p in shades}))
print("updated_at values", dict(C.Counter(p["updated_at"][:10] for p in P)), "| variants per product", dict(C.Counter(len(p["variants"]) for p in P)))
print("images per shade min/median/max", min(len(p["images"]) for p in shades), sorted(len(p["images"]) for p in shades)[len(shades) // 2], max(len(p["images"]) for p in shades),
      "| alt set", sum(i.get("alt") is not None for p in P for i in p["images"]))
print("shades with finish/color/collection tags", *(sum(any(t.startswith(ns + ":") for t in p["tags"]) for p in shades) for ns in ("finish", "color", "collection")))
print("color:clear", sum(tag(p, "color:clear") for p in shades), "| max product id digits", max(len(str(p["id"])) for p in P))
```

Expected output on the 2026-10-25 snapshot:

```
products 526 | shades 372 {'polish': 359, 'topcoat': 9, 'basecoat': 4} | bundles 46 | gifts 71 | skipped 37
gifts merging by handle 69 | manual: ['linear-holo-taco™-birthday-gift', 'royal-tea-blue-birthday-gift']
retired 118 unavailable 116 | retiring 14 | sold out (unavailable, not retired) 48 | buyable 208
on sale: shades 0 bundles 44 | shades with compare_at < price 6
SKU: HL-*-NP 285 | polish HL-*-NP 284 | unique SKUs 372
updated_at values {'2026-10-25': 526} | variants per product {1: 526}
images per shade min/median/max 3 10 20 | alt set 0
shades with finish/color/collection tags 346 361 372
color:clear 14 | max product id digits 14
```
