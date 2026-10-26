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
| Toppers | 9 `Top Coat` products, plus polish tagged `toppers` (Holo Taco's own topper tag: 44 single shades, 8 of them Top Coats) or `color:clear`: 14 shades carry that tag (1 Top Coat, 3 Base Coats, 10 listed as polish, two of those clear bases: `sticky-base`, `pink-smoothing-base`) |
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
  `<dialog>`, refocuses the picker field), `copy.js` (copy buttons), `tag.js` (copy the tag URL),
  and `chrome.js`, which every page loads: it turns the sticky search field into a material once it
  is stuck under the status bar. No bundler, no Node.
- **Vendored static assets** in `static/vendor/`: `htmx.min.js` and `zxing-wasm/` (reader build:
  `reader/index.js` and `share.js` as shipped, plus `zxing_reader.wasm`). Versions recorded in `static/vendor/VERSIONS.txt`, fetched by `scripts/vendor.sh` (a developer step);
  Renovate cannot update vendored files, so a refresh is a manual stage. There is no webfont: the UI
  is set in the system font (`system-ui`).
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
__main__.py, cli.py  python -m polished {serve | migrate | sync [--from-files … --sheet … --no-colours] | colours}
config.py            Settings (pydantic-settings, env prefix POLISHED_), section 12
db.py                connect(path), request-scoped connection dependency, transaction helper
migrate.py           numbered-SQL runner (serendip's, schema_version table); foreign keys off, a
                     migration may not leave more violations than it found
migrations/          001_catalog.sql … 007_release_sheet.sql
server.py            create_app(): middleware order, routers, templates, static, lifespan
web.py               Jinja environment, render(): full page vs partial, filters (money, thumb, dates, marked)
security.py          Origin check for unsafe methods, security headers and CSP, cache headers
auth.py              OIDC client, /auth/* routes, session helpers, deny-by-default gate
catalog/
  classify.py        product → shade | bundle | alias | skipped (+ MANUAL_ALIASES)
  parse.py           price parsing, tag splitting, shade kind, is_topper, hero image
  hashing.py         content_hash()
  fetch.py           polite Shopify client: fetch_feed(), rate limiter, User-Agent, 429 handling
  sync.py            apply_feed(): the feed in one transaction, absence accounting; SyncRunner: lock,
                     sync_run row, fetch or files, cooldown
  sheet.py           the release sheet: parse_sheet(), normalise_name(), fetch_sheet(), apply_sheet(),
                     merge_sheet_shade(), refresh_retired() (5.6)
  colour.py          extract_colours(): the polish colour from a photo; fill_colours(): the sync step
  scheduler.py       next_run_at(), catchup_due(), close_stale_runs(), Scheduler loop
shades.py            list/filter queries, status derivation, detail, manual shades
search.py            ranked, typo-tolerant name search and the <mark> spans of result rows (6)
bottles.py           bottle CRUD, owned rules
wishlist.py          wishlist CRUD, totals, cart permalink
gtin.py              normalise_gtin(), check digit
identifiers.py       resolve(), learn(), learn_printed(), printed-code normalisation, learned-code list
stacks.py            draft/commit, layers, templates, summary(), default_coats()
wheels.py            wheel CRUD and delete, slug generation, slot grid, tag URL, QR
tips.py              nail tips as SVG: render(layers), TIP_FIELDS, revision() for URLs and ETags (9)
routes/              home.py shades.py bottles.py wishlist.py lookup.py wheels.py stacks.py
                     tips.py sync.py pwa.py health.py   (thin: parse, call domain function, render)
templates/           base.html (tab bar, sheet), pages, partials (leading underscore: _shade_row.html …),
                     _icons.html (the `icon()` macro for the sprite)
static/              css/app.css (tokens and every component, docs/VISUAL.md), js/, vendor/,
                     icons/ (ui.svg sprite, nail-tip.svg mask, logo.svg,
                     favicon.svg and the PNGs scripts/make_icons.py draws from them)
```

Domain modules hold the SQL and take a connection; routes never write SQL. This keeps stage
tests (`tests/test_<module>.py`) independent of HTTP.

### 3.2 Page versus partial

`render()` returns a partial when the request has `HX-Request: true` and does **not** have
`HX-History-Restore-Request`; otherwise the full page. History restore must be a full page, and
`htmx-config` sets `historyCacheSize: 0` so private pages are not snapshotted into localStorage
and `includeIndicatorStyles: false` so HTMX injects no inline `<style>` (the CSP forbids it).
`responseHandling` also swaps a 422, so a form that fails validation can show its messages
(deviation 25); every other 4xx and 5xx is still not swapped.
All HTML responses carry `Cache-Control: private, no-cache` and `Vary: HX-Request,
HX-History-Restore-Request`, so Safari's back button never shows a partial.
`render(request, page, context, status_code, partial=None)` in `web.py` implements the rule: with a
`partial` template and an HTMX request it renders the partial, else the page. Templates see
`is_partial`, so a fragment can carry out-of-band updates (the result and filter counts) that the
full page already has in place. Money (`money`), thumbnail (`thumb`), tag-value (`label`:
"rose-gold" becomes "Rose gold"), phrase (`words`: a list of tag values as "Glitter, holographic")
and date (`day`: "2026-10-01" becomes "1 Oct 2026") are Jinja filters. `thumb(url, width)` adds
`width=` to a Shopify image URL; `thumb(url, width, height)` adds `width=`, `height=` and
`crop=center`, which the CDN answers with a true centre crop of exactly that size (verified on
`cdn.shopify.com`), so a row thumbnail keeps the bottle and drops the backdrop instead of zooming
with CSS.

**Look and feel.** `docs/VISUAL.md` is the spec for looks and this file wins on behaviour. In the
templates: `base.html` carries the five-tab bar (Home, Shades, Bottles, Wheels, Wishlist; a page sets
`{% set tab = "shades" %}` and a page without a tab, such as the offline and sign-in pages, gets no
bar), a skip link and the shared `<dialog id="sheet">`; each page opens with a large title
(`.title`, 34 pt bold) and, below the top level, a back link row. Icons are `{{ icon("name") }}`, a
`<use>` of `static/icons/ui.svg?v=<version>`. The CSP allows no inline style, so all styling is
classes in `app.css`; nothing sets a `style` attribute.

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
  product_id       integer unique references product (id),   -- null for source = 'manual' and 'sheet'
  source           text not null default 'holotaco' check (source in ('holotaco', 'manual')),   -- 007 adds 'sheet'
  kind             text not null check (kind in ('polish', 'topcoat', 'basecoat')),
  title            text not null,
  handle           text,
  sku              text,                                      -- not unique: Shopify does not enforce it
  search_text      text not null,                             -- lowercase, accent-folded title + tag values
  hero_image_url   text,                                      -- images[position = 1].src
  -- swatch_image_url text: added by 005 (4.3), the photo of the polish on a nail (the colour's source)
  -- swatch_hex, swatch_hex2, swatch_hex_src, swatch_override_hex text: added by 006 (4.3), the tip colour
  -- released_on, official_collection, sheet_retired, sheet_key: added by 007 (4.3), from the release sheet (5.6)
  price_cents      integer,
  compare_at_cents integer,
  available        integer check (available in (0, 1)),       -- null for manual shades
  published_at     text,
  is_topper        integer not null default 0,                -- topcoat, or polish tagged toppers or color:clear
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

`005_swatch_image.sql` (visual polish pass) is one statement: `alter table shade add column
swatch_image_url text;`. It is the photo that shows the polish on a nail, chosen at sync time by
`catalog/parse.py swatch_image_url(images, title)`; null when no photo qualifies. Since 006 it is
not shown anywhere: it is the source the colour is read from (5.5).

`006_swatch_colour.sql` adds four nullable text columns to `shade`: `swatch_hex` ("#rrggbb", the
dominant polish colour), `swatch_hex2` (a second, clearly different colour, for shifts and
duochromes), `swatch_hex_src` (the image URL the two were read from, so a new photo is read again)
and `swatch_override_hex` (the household's own colour; only the shade page writes it, the sync
never does). The tip colour is `swatch_override_hex`, else `swatch_hex`, else a neutral grey-mauve.

`007_release_sheet.sql` (the release sheet, 5.6) widens `shade.source` to `'holotaco' | 'manual' | 'sheet'`
and adds `released_on` (ISO date, the official release date), `official_collection` (text),
`sheet_retired` (0/1, from the sheet's Retired column) and `sheet_key` (the normalised sheet name the
shade matched; a partial unique index makes it unique among `source = 'sheet'` shades). SQLite cannot
alter a CHECK, so the migration **rebuilds `shade`** the way sqlite.org's ALTER TABLE section 7
prescribes: drop `shade_status`, create `shade_new` with every column in the old order plus the
four, copy every row with its id, drop `shade`, rename `shade_new`, recreate the three indexes and
the view. It is safe on a live database for three reasons: `migrate.py` now turns foreign keys
off, so dropping the old table cascades nowhere (`shade_tag` and `shade_identifier` delete on
cascade, and with foreign keys on, dropping would have emptied them); the whole file is one transaction,
so a failure leaves the old table; and the runner compares `pragma foreign_key_check` before and
after each file and rolls back a file that leaves more violations. Tables that reference `shade`
keep their `references shade (id)` text because the new table takes the old name. The migration runs
in the init container before the app starts, so nothing writes during the rebuild. Tested on a
populated database (`tests/test_migrate.py`) and on a copy of the development database (372 shades,
10 bottles: every row identical, `foreign_key_check` empty). A rollback is a restore of the PVC
snapshot, as for every migration; there are no down migrations.

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
- **The release sheet** (5.6) adds one more fetch after the shop pages: the Google Sheet's CSV
  export, once per run, never more.

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
   `swatch_image_url` is picked by filename (the feed has no alt text): lowercase words of the
   basename, split on punctuation, camelCase and digits, the shade's own title words dropped; a photo
   is rejected when a word starts with bottle, brush, swipe, corner, side, collage, spill or gif;
   ranks are macro, hand, swatch/nail/mani/ugc, then (older products, numbered page shots) pdp/layer
   at position 2 or later; best rank, earliest position wins. On the 2026-10-25 snapshot: 248 macro,
   40 hand, 40 swatch/nail/mani/ugc, 23 page shots, 21 none, so 351 of 372 shades have one. The
   column is written for new and changed shades. The content hash includes the image sources, so a
   shade from before migration 005 would stay without one: every sync also fills `swatch_image_url`
   for any shade where it is null from the feed already in memory (no extra request, no hash change).
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
   `retired`, `retiring`, `is_topper` (kind `topcoat`, or kind `polish` and tag `toppers` or `color:clear`:
   known false positives `sticky-base` and `pink-smoothing-base`, harmless in a layer picker). `retired` is then
   set to the tag **or** the release sheet's flag (`refresh_retired`, 5.6), so a changed product cannot undo the sheet.
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
| `sheet_only` | `source = 'sheet'` (checked first, after manual) | Not in the shop | no |
| `missing` | product `missing_since` set | Not listed | no |
| `retired` | `retired` | Retired (or "Retired, last stock" when `available`) | only if `available` |
| `sold_out` | not `available` | Sold out (plus "retiring" when `retiring`) | no |
| `retiring` | `retiring` | Retiring soon | yes |
| `available` | otherwise | In stock | yes |

Sale is `price_cents < compare_at_cents` (strict). Manual shades have no status and no price. A sheet-only
shade says "Not in the shop" whatever its retirement; it is in none of the Status filters.

### 5.4 Sync command and fixtures

`python -m polished sync` fetches live. `python -m polished sync --from-files p1.json p2.json
p3.json` applies local JSON pages with the same code path and no request to the shop, so local runs
and agents never touch it. The colour step (5.5) still downloads photos from the image CDN, so a
fully offline run adds `--no-colours`. Tests feed trimmed fixtures through `httpx.MockTransport`.

`tests/fixtures/feed_trimmed.json` is generated once by `scripts/make_fixtures.py` from the
snapshot (kept out of git) and committed: about 14 products, catalog fields only (title,
handle, type, tags, SKU, price, availability, two image URLs, no `body_html`), covering a normal
`HL-*-NP` polish, an older `HLT-NP-*` polish, a Top Coat topper with its birthday-gift copy, a
Base Coat, a bundle, a gift that merges by handle, a gift that needs the manual alias, a
retired shade, a soon-retiring one, a sold-out one, and an accessory. No single shade is on sale
in the real feed today, so the on-sale shade is a real shade whose `compare_at_price` the script
raises; the fixture README says so.

### 5.5 Polish colour (`catalog/colour.py`)

After the feed is applied and the run row is closed, the sync reads the colour of every shade whose
`swatch_hex_src` differs from its current source image (`swatch_image_url`, else `hero_image_url`):
all of them on the first run, afterwards only new shades and changed photos. One download each from
`cdn.shopify.com` (never holotaco.com) at `width=240`, 0.5 s apart, 8 s timeout, at most 450 per
run, and the step stops after 4 failures in a row. It never fails the run: an error is logged, the
colour stays as it was and the shade is tried again next sync. `sync --from-files` runs it too
(downloading from cdn.shopify.com) unless `--no-colours` is given.

`extract_colours(bytes, from_bottle, accent)` is pure (Pillow and numpy). Pixels come from the
middle of a swatch photo (32 to 68 percent across, 30 to 70 down: the painted nail of a macro or
hand shot), or from the glass of a bottle shot (the strip under the label and the two strips beside
it). Skin (a YCbCr range) and blown-out highlights are dropped; on a bottle shot the black backdrop
too; a mask that would keep under 8 percent of the pixels is not applied, so white and nude
polishes still get a colour. The rest goes through a 2-cluster k-means in Lab from a deterministic
start; `swatch_hex` is the median RGB of the larger cluster, and `swatch_hex2` the other's only when
it covers 20 percent of the pixels, is more than 15 delta-E away and (bottle shots) is not just the
dark side of the glass. For toppers, which are photographed over a base, the livelier cluster is
the first colour instead. On the 2026-10-25 snapshot: 372 of 372 shades, 223 with a second colour.

**Colour sampling.** A shade's colour comes from its swatch photo (centre box) and, only when that colour looks like skin, its bottle photo (lit glass under the cap). Skin is judged in CIE LCh: single pixels in a narrow band (hue 36–75°, L ≥ 22) are dropped before clustering; the cluster colour is skin-like at hue 20–70°, chroma 5–36, L 22–72. A skin-like swatch colour is replaced by the bottle colour when the bottle's is not skin-like or differs by ΔE > 20; a nude both photos agree on stays. Very dark grey pixels are dropped as backdrop when they are under 20% of the region, so black and dark-glitter polishes keep them. Base coats and clear top coats (no glitter, flakie or holographic finish) get the fixed sheer neutral `#f1e9e6` without sampling. Five shades whose photos defeat the sampler (Gold Flake Taco, Tax Haven, Solo Mission, Pink Steel, Trophy Life) take colours checked by eye from `colour.KNOWN_COLOURS`. `python -m polished colours --recompute [--only "A,B"]` re-samples ignoring `swatch_hex_src`, at the same 0.5 s spacing, and never writes `swatch_override_hex`.

### 5.6 Release sheet (`catalog/sheet.py`)

Holo Taco publishes its "Official Simply Holo Taco nail polish release list" as a public Google Sheet.
It has what the feed lacks: the **release date** (the feed's `published_at` is a re-publish date and
wrong for old shades), the **official collection name**, an official **Retired** flag (143 retired
against the shop's 118 tags) and shades the shop does not list (10 on 2026-10-25). It leaves out
top and base coats. `POLISHED_RELEASE_SHEET_URL` (default: the CSV export of that sheet; empty turns the
step off) is read once per sync run, **after the shop pages were applied and the run was closed**,
before the colour step. The fetch is one GET with the `polished/<version>` User-Agent, a 30 s
timeout, no retry and a 2 MB cap; Google answers the export URL with a 307 to `*.googleusercontent.com`,
which is followed (at most 3 hops, https only, only to Google or the configured host), so a fetch
is two HTTP requests. `sync --from-files` stays offline and skips the sheet unless `--sheet
SHEET.csv` gives a local copy (which is then read instead of fetched).

**Reading.** `parse_sheet(text)` finds the header row (the first with "Release date" and "Shade
name") and the columns "In Collection" and "Retired?" by name, so a moved column is fine; the
preamble above it (quoted cells with line breaks) and rows below it without a name or a date are
skipped. A row is `(key, name, released_on, collection, retired)`: the date is "Jul 6, 2019" read
to `2019-07-06`; **only the word `Retired` retires** (the column also says `Seasonal` on six
shades, which is not retirement); a name listed twice keeps its earliest date. `key` is the
**normalised name**: ™ and ® and apostrophes dropped, `&` read as "and", accents folded, case
folded, other punctuation one space ("Flakie Holo Taco™" and "Play Rosé" become "flakie holo taco" and
"play rose"). `ALIASES` maps a sheet key to a shop key for a real naming difference; it is empty
because on the 2026-10-25 snapshot all 364 matching names agree after normalising. A layout the
parser cannot trust raises `SheetError`: no header row, a header without a needed column, fewer
than `MIN_ROWS` (300) shades, or an HTTP error, redirect off Google, oversized or non-UTF-8 body.

**Applying** (`apply_sheet`, one transaction, called by `SyncRunner` and never allowed to fail the
run: a `SheetError` or any other exception is logged as a warning and the data stays as it was):
1. Each row is matched by key to a shop shade (`source = 'holotaco'`, a polish before a top coat of
   the same name). A match gets `released_on`, `official_collection`, `sheet_retired` and
   `sheet_key`. 364 of 372 match; the eight that do not (Sticky Base, Pink Smoothing Base,
   Quick-Dry Base, Peely Base, Smoothing Base, Long-Lasting Base, Matte Taco, Glossy Taco) are
   essentials the sheet excludes.
2. A row with no shop shade becomes a **sheet-only shade** (`source = 'sheet'`, `kind polish`, no
   product, handle, SKU, price, availability or photo; `search_text` the normalised name;
   `is_topper` when the name has the word Taco, Flake or Flakie: no false positive on the 364
   matches, 14 toppers without those words missed; the tip is neutral until the household sets the
   colour with Tip colour). It is created once (`sheet_key` is unique among sheet shades), follows its row on later runs,
   and is never deleted, even when the row leaves the sheet. More than 40 new sheet-only shades in one run
   is treated as a naming mismatch (the shop renamed its shades, say): `SheetError`, nothing written.
3. **Merge.** When a sheet-only shade's key matches a shop shade (the shop has started listing it),
   `merge_sheet_shade` moves its bottles, stack layers, learned codes and aliases to the shop
   shade, moves its wishlist entry (both wished: the lower priority number and the existing note
   win), keeps the household's tip colour unless the shop shade already has one, and deletes the
   sheet-only row. A test checks that every table with a foreign key to `shade` is handled.
   Between the shop run and the sheet step of the same sync the shade can exist twice; a failed
   sheet fetch keeps both until the next run.
4. `retired` is the shop's `collection:retirement` tag **or** `sheet_retired`
   (`refresh_retired`, run last by both the shop apply and the sheet apply, so a changed product
   cannot undo the sheet). On the snapshot: 118 tagged, 134 of the matches retired by the sheet, 140
   shop shades retired by either (six are tagged by the shop and not retired by the sheet), 9 of 10
   sheet-only shades retired.

The shop's `published_at` and its tags are untouched, and "Newest" (`sort=newest`, Home's "New and
in stock") still reads `published_at`; `released_on` is only for the sort and the facts below.

## 6. Searching and browsing

- **Name search is ranked and forgiving (`search.py`).** A query is tokenised like the stored text
  (`search.tokens`: lowercase, accent-folded, split on anything that is not a letter or digit, so
  "™", hyphens and accents do not matter). Python scores every shade's title and `search_text`
  (title, handle, tag and collection values) on each query: 372 rows take about 1 ms warm and 2 ms
  cold, so there is no index and no cache to go stale (the folded titles are memoised by string, which
  needs no invalidation). A shade matches in the first of these tiers that fits:
  0 the title is the query; 1 the title starts with it; 2 every query word is a whole word of the
  title; 3 every query word starts a title word ("holo magn"); 4 every word occurs in `search_text`
  (the old `LIKE '%word%'` rule, so tags and collections still find shades); 5 **fuzzy**: every word
  either occurs in `search_text` or is within a few edits of a title word, or the query without its
  spaces is part of the title without its spaces ("onecoat" finds "One-Coat Black"). Edits are
  Damerau-Levenshtein distance with adjacent swaps counting once ("magentic" is one edit from
  "magnetic"), per query word: none under 4 letters, one for 4 to 7, two from 8. (No trigram index:
  at this size the edit distance is exact, explainable and fast enough; its pair results are memoised.)
  Within a tier: fewer edits (only tier 5 has any), then the shorter title, then, for the home search
  and the pickers only, owned before wishlisted before the rest, then the title. So "magnetic taco"
  lists Magnetic Taco, then Holo Magnetic Taco, then shades that only have the words in tags.
  Ownership is a tie-break, not a tier: it no longer lifts a longer title above a better match.
- A search with words ranks the result by this order whenever the sort is "Name" (the default);
  with another sort the matches keep that sort's order. Words that are only punctuation are no
  search at all (the list is whole). The same ranking serves the home search (`shades.search`, 30
  rows and the total), `/shades?q=`, the builder picker (`shades.pick`, narrowed by Owned,
  Toppers or All) and the learn picker. An empty query in the builder lists the scope, owned first.
- **Near-duplicates stay tellable apart.** Result rows carry `marks`, the character spans of the
  title the query matched (`search.marks`: a whole word for an exact or near match, the typed part of
  a word the query only starts; nothing for a tag or missing-space match). The `marked` filter
  (`web.py`) escapes the title and wraps those spans in `<mark>`, so "Holo <mark>Magnetic</mark>
  <mark>Taco</mark>" shows what differs from "<mark>Magnetic</mark> <mark>Taco</mark>". Minimal markup;
  the browser's default `mark` look stands until the stylesheet gives it one.
- Filters on `/shades`, one GET form (so the URL is the state and works without JavaScript):
  `finish` and `color` (multi-select, any-of within a namespace, AND between filters),
  `collection` (one: an official collection name from the release sheet, or one of the shop's collection tags; the
  panel's select lists the official names under "Official collections" and the tags under "Shop tags", and only the
  tags until the sheet has been read), `kind` (`polish|topper|base`; `topper` is `shade.is_topper`, `polish` is a
  polish that is not a topper, `base` is a base coat, so the three partition the catalog),
  `status` (`buyable|retired|sold_out`, the derived status of 5.3: `buyable` is the "Buyable
  yes" rows, `retired` and `sold_out` the rows with that status; a missing shade is in none of
  them), `owned` (`any|owned|not_owned|wishlist`, stage 4), `sort` (`name|released|newest|price`;
  released = the sheet's `released_on`, newest first, labelled "Release date, newest first"; newest = `published_at`,
  labelled "Recently listed"; shades without a date or price sort last), `page` (40 a page,
  a "Load more" button, not infinite scroll). A value the page does not know means "no filter".
  The form sits in a `<details>` next to the sticky search field; the panel drops down over the
  list, always shut on load (the badge on its button counts the active filters), and ends in a bar
  with "Clear all" and the one filled button "Show N shades", which only closes the panel (the list
  already follows the filters; the button's count rides along out of band). A change or 200 ms of typing sends the form with `hx-get`, the fragment (rows, Load more
  and the two counts as out-of-band spans) replaces `#shade-list`, and `hx-push-url` keeps the URL.
- A shade row (`_shade_row.html`, one line, class `shade-row`) shows the painted tip (`_tip.html`,
  40 by 66), the title with a pink ♥ right after it when the shade is wishlisted and the price at the
  trailing edge, and under them the status word (`--bad` or `--warn`, no fill), up to three finishes
  (plus "Topper") and, under the price, "×N" as a footnote when `shade_status.owned_count` is above 0
  (its `aria-label` is "Owned ×N"); it opens the shade. A bottle photo appears only in the shade
  page's strip and in the lookup result card.
- The detail page shows the images (every `images[]` entry of the product's stored feed JSON) in
  a horizontally scrolling, scroll-snapped strip; under it the shade's painted tip (`tip-xl`, 96 by 158,
  on the plate: `--velvet` in dark) beside the title in the display face, and on the subhead line the price (with the compare-at price and a "Sale" chip
  when `price < compare_at`), "Owned ×N" and the status word. Then the actions, the bottles, a quiet
  list of Finish, Colour and Collections with outlined chips that link back to the filtered list,
  "Swatched on" rows (the stack's composite tip and "Holos, slot 1"), the Tip colour disclosure
  (section 9), and a link to `POLISHED_STORE_URL/products/<handle>` (replaced by "No longer
  listed" for a missing shade). A shade with a release date has a footnote under the subhead,
  "Released 6 Jul 2019" (", retired" is added for a sheet-only shade the sheet calls retired), and its official
  collection is the first chip of the Collections row, linking to `/shades?collection=<name>`. A sheet-only
  shade has no photo strip (the tip at `tip-l` is the hero), no price, no SKU and no store link; its subhead
  says "Not in the shop". In list rows the same words stand where the price would, in `--ink-2`.
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

Whitespace is removed anywhere in the value (a code typed in groups still reads), and only ASCII
digits count. `normalise_printed(raw) -> str | None`: strip, uppercase, remove spaces; all digits gets the
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
  override pointing at `/static/vendor/zxing-wasm/zxing_reader.wasm`, loaded on the first scan),
  formats `EAN13`, `UPCA`, `EAN8`, `tryHarder` on, frames cropped to the framing guide (the
  guide's box mapped through the video's `object-fit: cover`) at about 6 per second. A code is
  accepted after two identical consecutive reads. `BarcodeDetector` is feature-detected as a
  two-line branch and not tested (iPhone only).
- Fallback text action "Take a photo instead": `<input type="file" accept="image/*"
  capture="environment">`, decoded from the still, which is sharper than video frames for a
  small printed barcode.
- The scanner is a non-modal `<dialog id="scanner">` laid over a 4:3 viewfinder (radius 16) at the
  top of `/lookup` (video, framing guide, Close); under the viewfinder a caption ("Point at the
  barcode under the bottle", also the status line). Until the camera runs the viewfinder shows an
  idle tile with the one `[data-scan-open]` button ("Scan the barcode"); `/lookup?scan=1` (what the
  Scan buttons on home and `/bottles` link to) opens the camera at load. Esc and Close end it. When
  the camera cannot start (no secure context, denied, none, busy) a note on the page says which, and
  names the photo action and the typed field. Below sit the one field ("Type the digits, a P code, or
  a name"), "Take a photo instead", the result area and the "Learned codes" row.
- On accept it vibrates where supported, flashes the guide, stops the camera at once, and calls
  `htmx.ajax('GET', '/lookup/resolve?q=<digits>&via=scan', '#lookup-result')`.
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
       the id_token is required: a token response without one, or a session without a nonce, is
       refused (400). aud must equal or contain POLISHED_OIDC_CLIENT_ID (checked in polished,
       because authlib only checks azp). claims = id_token claims; if "groups" is absent there,
       call the userinfo endpoint and merge only if its sub equals the id_token sub (else 400);
       the id_token's values always win, userinfo never overwrites sub.
       Any OAuthError, JOSE error (bad signature, expired, wrong nonce/iss/aud) or refusal above
       → login_next cleared, 400 "Sign-in failed" page, no session.
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
  manifest can never run open by accident, and it logs a warning on every start. In none mode
  `POLISHED_HOST` defaults to `127.0.0.1` and must be `127.0.0.1`, `::1` or `localhost` if set;
  startup is refused otherwise, so a dev config can't listen on the network. `oidc` mode keeps
  the `0.0.0.0` default.
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
- **Wheel page `/w/<slug>`** (the canonical page; `/wheels` links to it): the ring plus the list
  of docs/VISUAL.md 5, replacing the 4-column grid. The ring is slots 1..20 as nail tips around a
  hub, a filled tip shows the whole stack as one drawing (`/tips/stack/<id>.svg`, below), the hub shows the filled count ("13") over "of 20" (the title above it already names the wheel), the
  ring has one radius (150px, the full width of a 390pt phone; it shrinks to fit below 400pt) for any
  slot count, a 1.5px hairline circle runs through the stems of the tips like the plastic ring of a real
  wheel, an empty slot is a `--fill` tip with its number and no foil (foil is for `?hl` and the save
  sweep only), a slot with an open draft shows a "draft" dot; below it a plain list of the filled
  slots (the composite tip, name and date) reads each stack without squinting. Tapping a tip or a list row opens the stack builder (section 10). The page ends in one quiet row of four text actions, "Tag and QR code", "Rename", "Archive" (confirmed) and "Delete wheel" (red text); Rename opens a small sheet (`GET /wheels/{id}/rename`, saved with `POST /wheels/{id}`, which answers `sheetClose` and swaps the title out of band). `?hl=<shade_id>` highlights every slot whose stack contains that shade
  and scrolls to the first (`#slot-12`), which is what "Swatched on" links on the shade page use.
- **Nail tips are drawn, never photographed (`tips.py`, `routes/tips.py`).** A tip, a mini tip, a
  builder layer tip and the preview on the shade page are an `<img>` of a 102×168 SVG that CSS
  clips to the tip shape (`object-fit: cover`). `GET /tips/shade/<id>.svg` draws one shade and
  `GET /tips/stack/<id>.svg` a whole stack in painting order; the URL carries `?v=<revision>` (a hash of
  everything drawn), so the answer is `private, max-age=31536000, immutable` with an ETag, and a changed
  colour is a new URL. The drawing uses presentation attributes only (no `style`, no script, no
  external reference), is seeded by the shade id (the same shade looks the same everywhere) and
  reads the shade's colour (`swatch_override_hex`, else `swatch_hex`, else neutral; `swatch_hex2` as a
  second colour), its finish tags and `is_topper`:
  creme is flat with a gloss; jelly is the colour at about 70 percent over what is below, darker toward the free
  edge; shimmer adds fine dust; metallic, chrome and reflective a light-to-dark gradient of the hue;
  holographic and iridescent two soft spectrum sweeps (and the second colour sweeping in); glitter dots
  and four-point stars; flakie translucent iridescent chips; magnetic a blurred cat-eye band; thermal a
  gradient from the first colour to the second; matte has no gloss, everything else one gloss streak.
  A stack goes on top of the last opaque layer (the ones below are covered); a jelly tints what is
  below; a topper or a clear base coat adds only its finish, so "One-Coat Black + Flakie Holo Taco"
  is flakes on black. With nothing opaque below, layers go on a sheer nude, so a lone topper shows.
  Every list shows tips (shade rows, the Home shelf, picker results, the wishlist, bottle groups); the
  bottle photo is kept only in the shade page's strip and the lookup result card.
  **The light on a tip is CSS** (`_tip.html`: `.tip` > `.tip-face` > `<img>`; VISUAL.md section 5): the
  drawing keeps the paint (base, finish, the gloss stripe, the small highlight at (66, 30), the dome whose
  edge is .18) and the page adds the contact shadow, the die-cut edge, the occlusion, the specular pool and
  the rim, because those depend on the board, the colour scheme and where the light is. `tips.DRAWING_VERSION`
  goes into `revision()`: bump it whenever `render()` draws differently, since the image URLs are cached
  for good and only a new revision makes a browser fetch the new drawing.
- **The ring at small sizes** (`_mini_ring.html`, the same `.slot` and `.tip` CSS with `--ring`,
  `--slot-h` and `--rail` set per size, tips only, nothing to tap): `.ring-home` is 200px (radius 78,
  tips 20 by 32) and links to the wheel from Home with "Holos, 13 of 20"; `.ring-mini` is 72px (radius 28,
  tips 9 by 14) in front of each wheel in the Wheels list; at these sizes the tip keeps only its mat (no
  specular pool or rim). A tip is never wider than its pitch on the ring,
  so a 40-slot wheel gets narrower tips instead of overlapping ones. Home shows the wheel whose saved or
  draft swatch changed last (`wheels.most_recent`; the newest wheel when none has a swatch, a ring of
  unpainted tips and "No wheels yet" when there is no wheel). Opening a wheel is not recorded.
- **Tip colour on the shade page:** a quiet "Tip colour" disclosure at the foot (the drawn tip, where the
  colour came from, a chevron) that opens an `<input type="color">`
  prefilled with the effective colour, Save and (when set) Reset (open by itself after a 422). `POST /shades/<id>/tip-colour`
  takes `hex` (`#rrggbb`, else 422 with the page) or `reset=1`, answers 303 to the shade and writes
  only `swatch_override_hex`.
- **The Wheels list** has the "+" in the title row (a `<details>` summary pulled up into it; it opens
  the create form under the title and turns into ×; open by itself after a failed create) and a grouped list
  of wheels, each a mini ring, the name and "13 of 20, 2 drafts". With no wheel the page is the unpainted ring,
  "No wheels yet", one line and the form.
- **Tag page `/wheels/<id>/tag`:** the full URL with a Copy button, the QR code, and the NFC
  Tools steps (Write → Add a record → URL/URI → paste → Write; Web NFC writing does not exist
  on iPhone). Shown right after a wheel is created.
- **QR:** `GET /wheels/<id>/qr.svg`, generated on the fly by `segno` (`error='m'`, scale 8,
  border 2, no XML declaration), `image/svg+xml`, `Cache-Control: private, max-age=86400`. The
  QR carries the same URL as the tag, so a failed tag, a laptop or a printed sticker all work;
  the iOS camera opens it natively.
- **Moving a tag:** "New tag URL" regenerates the slug (the old tag then 404s once logged in);
  "Take the tag of…" on wheel B swaps slugs with wheel A, so a tag stuck on a discarded wheel can
  point at its replacement without rewriting it. An archived wheel's page shows a banner with Restore,
  the take-tag action and "Delete wheel".
- **Deleting a wheel** (Jan: a test wheel was "just stuck there") is for good and asks first. "Delete
  wheel" (the foot row, and the archived banner) opens a small sheet (`GET /wheels/{id}/delete`): "Delete
  Test?", "Its 3 swatches go too. Its tag and QR code stop working. This can't be undone." (with no
  swatches: "It has no swatches. This can't be undone."), a red "Delete wheel" button and Cancel.
  The button posts `confirm=yes` to `POST /wheels/{id}/delete` (HX-Redirect to `/wheels`; a plain form gets
  a 302); without that field the answer is 400 and nothing is deleted, an unknown wheel is 404, and the
  Origin check applies like any POST. `wheels.delete` runs in one transaction: it removes the wheel (its slot
  rows go by `on delete cascade`), then every saved and draft stack those slots pointed at (the foreign key
  runs from slot to stack, so the stacks do not cascade; their layers do). Shades, bottles and other wheels
  are untouched, and the wheel's `/w/<slug>` then answers the 404 page (after sign-in, like any unknown
  slug). Archive stays the way to put a wheel away without losing it.
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
   the existing `draft_stack_id` if there is one (a "Resumed your draft." footnote in the head), else creates a
   draft `stack` containing a copy of the slot's saved layers (or none) and stores it in
   `draft_stack_id`. The partial is the sheet; `sheet.js` calls `showModal()` on the `<dialog>`
   when `#sheet-body` is swapped.
2. **Sheet layout, top to bottom** (bottom-anchored `<dialog>`, `max-height: 92dvh`; the head
   with the live summary and the Save footer are sticky, the results scroll in their own area;
   buttons are at least 44 pt; see deviations 60 to 64). Layers are
   listed in painting order, **Base at the top**, as the advice recommends:

   ```
   [tip]  Slot 12                                             [Cancel]
   [tip]  Holos                       <- the stack's composite tip, 72x118
   [tip]  One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco   <- live summary
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
   the swap parks one layer on `ord = count + 1` as a temporary value because `(stack_id, ord)` is unique and `ord >= 1`. No
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
  The mark is one holographic nail tip on plum (`static/icons/logo.svg`, docs/VISUAL.md 11). The
  tab icon is `favicon.svg` (the nail without gloss, on a rounded plum tile; no style element and no
  media query) with `favicon-32.png` as the fallback link. The PNGs (180 apple-touch, 192 and 512
  rounded, 512 maskable, 32 favicon) are committed and drawn from the two SVGs by
  `scripts/make_icons.py` with Chromium through Playwright. The manifest's `background_color` is the
  icon's plum so the splash screen is the icon on its own ground, its `theme_color` the light page
  colour; the page's two `theme-color` metas follow the colour scheme.
- `GET /sw.js` is served from the root so its scope is `/`, with `Cache-Control: no-cache`. It
  has three jobs: precache `/offline`, `app.css`, `htmx.min.js`, `register-sw.js`, `chrome.js` (the stuck search bar, the filter panel's Show button), the
  icon sprite, `favicon.svg`, and the 32, 180 and 192 px icons into
  `polished-static-<version>`; serve `/static/*` cache-first (templates append `?v=<version>`,
  so a release changes the URLs); answer a failed navigation with `/offline`. It never caches
  HTML, partials, API responses or cross-origin requests, never touches non-GET requests, and
  deletes old caches on `activate`. No offline writes, no background sync.
  `sw.js` is a Jinja template (it takes the version) and answers `HEAD` as well as `GET`. A server
  whose version is `dev` leaves `/static` to the network, since its `?v=dev` URLs never change.
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
| `HOST`, `PORT` | `0.0.0.0` (`oidc`), `127.0.0.1` (`none`, loopback only); `8080` | Listener |
| `STORE_URL` | `https://holotaco.com` | Shop base for the feed and cart permalinks |
| `SYNC_ENABLED` | `true` | Scheduler on/off (the manual button and CLI still work) |
| `SYNC_HOUR`, `SYNC_JITTER_MIN` | `6`, `30` | Daily run, local time |
| `SYNC_MIN_INTERVAL_S` | `1.0` | Gap between requests; values below 1.0 are rejected at startup |
| `SYNC_MANUAL_COOLDOWN_S` | `3600` | Minimum time between runs started by the button |
| `RELEASE_SHEET_URL` | the CSV export of Holo Taco's release list (Google Sheets) | Read once per sync after the shop pages (5.6); empty turns it off |
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
| GET | `/` | Home: large title with the icon, search, the most recently touched wheel as a 200px ring, recent bottles as tips, one line of counts as links, a short grouped list (Browse all shades, Toppers, New and in stock, More) | full page | 3 |
| GET | `/more` | Add a shade by hand, Catalog sync, Learned codes, and Sign out under "Signed in as …" | full page | 2b |
| GET | `/search` | Typeahead rows. Params `q`, `ctx` (`home`, `stack`, `learn`), `filter` (`owned/toppers/all`), `stack_id`, `kind`+`value` for `learn` (422 without a valid code). Row action depends on `ctx`; `home` in stage 3, `learn` in 5, `stack` in 7. Always rows only (the page that asked is on screen), nothing for an empty query. `home` adds a "Look up “259” as a code" link when `q` is all digits or a P code. Ranked and typo-tolerant (section 6); rows mark the matched words with `<mark>` | partial | 3 |
| GET | `/shades` | Browse list with filters (section 6) | full page; P = rows + Load more | 3 |
| GET | `/shades/{id}` | Detail: images, tags, price/status, product link; stage 4 adds bottles and wishlist, stage 6 "Swatched on" | full page | 3 |
| GET | `/shades/new` | Manual shade form (gifted non-catalog bottle) | full page / P | 4 |
| POST | `/shades` | Create manual shade (title, kind) | 302 to the shade | 4 |
| GET | `/wheels` | The Wheels tab (section 13.5) | full page | design |
| GET | `/sync` | Last runs, counts, Sync now | full page | 2 |
| POST | `/sync/run` | Start a manual run (409 running, 429 cooldown) | P status | 2 |
| GET | `/sync/status` | Status box; polls every 2 s while running | P | 2 |

### 13.3 Bottles and wishlist

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/bottles` | My bottles grouped by shade; filters `state`, `archived` | full page / P | 4 |
| GET | `/bottles/history` | Purchase history: years, months, rows; Collection / History switch | full page | history |
| GET | `/shades/{id}/bottles/new` | Add-bottle form (P code field, state, date, price, notes) | P (sheet) | 4 |
| POST | `/shades/{id}/bottles` | Create; learns the P code (stage 5) | P `#bottles`, `HX-Trigger: sheetClose` | 4 |
| GET | `/bottles/{id}/edit` | Edit form | P (sheet) | 4 |
| POST | `/bottles/{id}` | Update | P bottle card, `HX-Trigger: sheetClose` | 4 |
| POST | `/bottles/{id}/state` | Set full / half / low / empty | P bottle card | 4 |
| POST | `/bottles/{id}/archive` | `archived=0/1`; called from the edit sheet | P bottle card (`ctx=shade`) or an empty body that swaps the row away (`ctx=list`); `HX-Trigger: sheetClose` | 4 |
| POST | `/bottles/{id}/delete` | Hard delete a mistaken entry (`hx-confirm`) | P (empty) + `sheetClose` | 4 |
| GET | `/wishlist` | Items by priority, total (all, and buyable), cart box | full page | 4 |
| POST | `/shades/{id}/wishlist` | Add (`priority`, default 2; an existing item is kept) | P action bar | 4 |
| GET | `/wishlist/{id}/edit` | The row's sheet: note and Remove | P (sheet) | 2a |
| POST | `/wishlist/{id}` | Priority (1 to 3) and note, from the row's sheet (an empty note clears it) | P `#wishlist`, `HX-Trigger: sheetClose` | 4 |
| POST | `/wishlist/{id}/priority` | Priority alone, from the row's menu; the note stays | P `#wishlist` | 2a |
| POST | `/wishlist/{id}/delete` | Remove (`ctx=shade` from a shade page, `ctx=list` from the row's sheet) | P `#wishlist` + `sheetClose` / action bar | 4 |
| GET | `/wishlist/cart` | Permalink for buyable items up to `max_priority` | P cart box | 4 |
| GET | `/wishlist/bought` | "I bought these" sheet; `max_priority` picks what starts ticked | P (sheet) | history |
| POST | `/wishlist/bought` | `item` (ids, repeated), `price-<id>`, `bought_on`; one full bottle per item, items removed, one transaction | P `#wishlist` with a confirmation, `HX-Trigger: sheetClose`; 422 retargets the sheet; unknown item 404 | history |

Cart permalink: `<POLISHED_STORE_URL>/cart/<variant_id>:1,<variant_id>:1,…` (default
`https://holotaco.com/cart/…`), buyable items only (`shades.status().buyable`: not missing, and
available), quantity 1, in list order (priority 1 first, then the order added), opened with
`target="_blank" rel="noopener"`. `max_priority` (1 to 3, default and out-of-range 3) limits it to
the first priorities. Verified 2026-10-25 with one request: `https://holotaco.com/cart/16924152004698:1`
answers 301 to `https://www.holotaco.com/cart/16924152004698:1?cart_link_id=…`, then 302 to
`https://www.holotaco.com/checkouts/cn/…`. So the permalink opens the Shopify **checkout** with the
items in it, not the cart page; the button reads "Open in Holo Taco checkout". The head of the page
(`_cart_box.html`) is one line, "$78.50 for 5 shades in stock", a footnote "1 not buyable" when
items on that part of the list cannot be bought, the checkout button, the text actions "Copy list"
(the shade names, one per line, for ordering by hand, from a hidden textarea that is shown and
selected where the clipboard is refused) and "I bought these", and the include filter (a segmented
control of three) under them.

Every route in this section except `GET /bottles` and `GET /wishlist` answers with its fragment
whether or not `HX-Request` is set, as `/search` does. A bottle
form that fails validation answers 422 with `HX-Retarget: #sheet-body`, so the messages appear in
the sheet. `POST /wishlist/{id}`, `/wishlist/{id}/priority` and `/wishlist/{id}/delete` return the
whole `#wishlist` body (totals, checkout box and groups all change with a priority), not one row; the delete from a shade
page (`ctx=shade`) returns the shade's action bar instead. Bottle cards and the new bottle list
carry the shade page's action bar as an out-of-band copy when `ctx=shade`, because the bar's
"I have this" / "+ Add bottle" label and the "owned ×N" badge follow the bottles.

### 13.4 Identifier lookup

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/lookup` | Viewfinder, one text field, "Take a photo instead", result area, Learned codes; `?q=` resolves without JavaScript, `?scan=1` opens the camera | full page | 5 |
| GET | `/lookup/resolve` | `q`, `via=scan/typed` → `match`, `suggestion`, `unknown_code`, `unknown_printed`, `invalid_code`, `results` (section 7.2) | partial | 5 |
| POST | `/identifiers` | Learn `kind` (`gtin`/`printed`), `value`, `shade_id`; a known code keeps its shade and says so | P "Saved" + the match with "+ Add bottle" | 5 |
| GET | `/identifiers` | Learned mappings | full page | 5 |
| POST | `/identifiers/{id}/delete` | Delete a mapping; `ctx=lookup` ("This isn't it") turns the result back into "New barcode" | P (empty, or the result) | 5 |

`/lookup/resolve`, `POST /identifiers` and its delete answer with their fragment whether or not
`HX-Request` is set (deviation 24). The add-bottle sheet takes `?ctx=lookup&printed_code=P259`
(pre-filled code; the form then posts `ctx=lookup` and the result area shows "Added …" with
"Scan another").

### 13.5 Wheels and stacks

| Method | Path | Purpose | Response | Stage |
|---|---|---|---|---|
| GET | `/wheels` | Wheels with a mini ring each (archived behind a row), new-wheel form behind the "+" | full page | 6 |
| POST | `/wheels` | Create (name, slot_count default 20) | 302 `/wheels/{id}/tag` | 6 |
| GET | `/w/{slug}` | The wheel page; NFC and QR target; `?hl=<shade_id>` | full page | 6 |
| GET | `/wheels/{id}/rename` | The rename sheet (404 for no such wheel) | P sheet | 2b |
| POST | `/wheels/{id}` | Rename | P header | 6 |
| POST | `/wheels/{id}/archive` | `archived=0/1` | 302 | 6 |
| GET | `/wheels/{id}/delete` | The delete confirmation sheet (404 for no such wheel) | P sheet | 84 |
| POST | `/wheels/{id}/delete` | Delete the wheel, its slots, stacks and layers; needs `confirm=yes` (400 without), 404 unknown | 302 `/wheels` (HX-Redirect for htmx) | 84 |
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
| GET | `/tips/shade/{id}.svg` | The painted-nail drawing of a shade (`?v=` ignored) | `image/svg+xml`, ETag | polish |
| GET | `/tips/stack/{id}.svg` | The drawing of a stack's layers in order | `image/svg+xml`, ETag | polish |
| POST | `/shades/{id}/tip-colour` | `hex=#rrggbb` or `reset=1` | 303 shade page, 422 | polish |

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
14. **Single flight also reads the `running` row (stage 2).** `SyncRunner.begin()` takes the
    `asyncio.Lock`, then in one transaction refuses (409) if a `running` row younger than an hour
    exists (a run in another process, e.g. the CLI), refuses a manual run (429) inside the
    cooldown, and inserts the `running` row. A `running` row older than an hour never blocks, even
    before the startup sweep has closed it. The CLI (`trigger='cli'`) skips the cooldown.
15. **An empty feed is an error**, not a run: `apply_feed` raises before touching the database
    when no product has a variant, so a broken response can never become the baseline of the 70%
    trust check. Redirects are followed only within the shop's own site (`holotaco.com`, with or
    without `www.`), at most three hops, each one throttled like a request.
16. **The 409 and 429 of `POST /sync/run` are mostly unreachable from the page.** htmx 2 does not
    swap 4xx responses by default, so the status box disables "Sync now" while a run is going or
    the cooldown lasts; the status codes (with the message in the partial) still answer races and
    plain `curl`. A form posted without HTMX is redirected (303) to `/sync`.
17. **The fixture has 16 products**, not "about 14": the unresolved-alias case (a manual-alias
    gift whose shade is absent) and the `color:clear` topper needed two more.
18. **`kind` filter values are `polish|topper|base`** (stage 3), not the column's `polish|topcoat|
    basecoat`: "topper" is `shade.is_topper` (top coats, flakie and glow polishes, clear bases),
    and the three values partition the catalog so the counts add up. The status filter keeps the
    four DESIGN values; `retiring` and `missing` are row labels, not filters.
19. **Stage 3 has more templates than PLAN.md lists:** `_shade_rows.html` (rows plus Load more,
    the fragment of `/shades`) and `not_found.html` (an unknown shade id is a 404 page, not JSON).
    `render()` takes a `partial=` template and passes `is_partial` to templates (section 3.2).
20. **`/search` always answers rows only**, with or without `HX-Request`, and refuses a `ctx` other
    than `home` with 422 until stages 5 and 7 add theirs (stage 5 added `learn`). An empty query returns an empty body.
21. **The service worker caches no `/static` file in a `dev`-version server**, and precaches
    `register-sw.js` and the 180 and 192 px icons (not the 512 ones): section 11. `/manifest.webmanifest`, `/sw.js` and
    `/offline` answer `HEAD` so `curl -I` works.
22. **The status label of a sold-out, soon-retiring shade is "Sold out, retiring"** (5.3 says
    "Sold out (plus 'retiring')").
23. **The trimmed fixture cannot exercise three acceptance checks of PLAN.md stage 3:** no fixture
    shade matches "spirit" or "black" (`/shades?q=spirit` shows the empty state), and it has no
    in-stock holographic shade (its two holographic shades are retired or sold out, so
    `finish=holographic&status=buyable` counts 0 rows). `tests/test_routes_browse.py` adds
    synthetic in-stock holographic shades for the last; the local snapshot answers all three
    (Spirit Fingers found, 22 "black" rows, 62 buyable holographic, 48 toppers of 372).

24. **Fragment routes answer with the fragment even without `HX-Request`** (stage 4), as `/search`
    does: bottle and wishlist POSTs, the add and edit sheets and `/wishlist/cart`. PLAN.md's curl
    checks send no `HX-Request` and expect the partial (`P259` in the body). Only `/bottles`,
    `/wishlist`, `/shades/new` and the shade pages follow the page-or-partial rule of 3.2.
25. **A 422 is swapped by htmx** (stage 4). `htmx-config` gets a `responseHandling` list that is
    htmx's default plus `422`, because a bottle form with a bad price or date comes back with its
    messages and `HX-Retarget: #sheet-body` (deviation 16 still holds for 409 and 429).
26. **The P code is normalised on save, and a code that does not look like one is kept** (stage 4).
    PLAN.md says "stored uppercase, normalised later"; the acceptance check and the quick-entry UX
    need `259` to be stored as `P259` now. `identifiers.normalise_printed` (7.1) exists with only
    that function; stage 5 adds `resolve()` and `learn()`. A value that fails the 7.1 pattern
    (`^[A-Z]{1,2}\d{1,5}$`) is stored uppercase without spaces instead of being refused, since the
    format of every code a bottle may carry is not known and a bottle is never lost over its code.
    The field uses `inputmode="numeric"`, so it shows and takes the digits only (`P259` is shown as
    `259`).
27. **The wishlist routes return the whole `#wishlist` body, not a row** (stage 4), and the checkout
    box falls back to "Everything" after a change, because a priority or a removal changes the
    groups, the totals and the permalink together. A note edit swaps nothing.
28. **Stage 4 has more templates and one more script than PLAN.md lists:** `_bottle_card.html`,
    `_bottle_groups.html`, `_bottle_swap.html` (card plus the out-of-band action bar),
    `_oob_actions.html`, `_shade_actions.html` (the two primary buttons), `_wishlist.html`,
    `_wishlist_row.html`, and `static/js/copy.js` ("Copy the list"). `sheet.js` is loaded by the
    shade page and `/bottles`, `copy.js` by `/wishlist`; the `<dialog id="sheet">` is in
    `base.html`. Deleting a bottle lives in its edit sheet (`hx-confirm`), archiving on the card.
29. **The trimmed fixture cannot show a permalink from shade 2 alone:** shade 2 is Gold Play
    Button (retired, sold out), so PLAN.md's `wishlist/cart` check prints nothing for it, which is
    the buyable-only rule at work. Adding a buyable shade (1 or 6) prints the permalink; the
    snapshot (372 shades) prints one for several. `tests/test_wishlist.py` checks the exact string
    with sold-out, retired-unavailable, no-longer-listed and manual shades in the list.
30. **`POST /shades` answers 302 and a shade added by hand has `kind` polish, topcoat or basecoat**
    for the form values polish, topper, base (a topper is a `topcoat` with `is_topper = 1`), so the
    kind filter of 6 finds it. The form is a plain POST, not HTMX.
31. **The top bar gains Bottles and Wishlist** next to Shades, and the shade list gains "Add by
    hand" (also offered by an empty search).

32. **zxing-wasm 3.1.6 is vendored with the package's own layout** (stage 5): `reader/index.js`
    imports `../share.js`, so the two files sit under `static/vendor/zxing-wasm/` as shipped
    (unmodified, sha256 in `VERSIONS.txt`) and `zxing_reader.wasm` next to `share.js`, which gives
    the `/static/vendor/zxing-wasm/zxing_reader.wasm` URL of PLAN.md. The package's default wasm URL
    is a jsDelivr CDN; `scanner.js` always overrides it with `locateFile`. Format names in this
    version are `EAN13`, `UPCA`, `EAN8`. `scripts/vendor.sh` fetches the npm tarball and checks its
    sha256 (it also re-fetches htmx 2.0.11 with its recorded hash). 3.1.6 was released six days
    before this stage; a pin a few weeks older would have been as good, and a refresh is manual.
33. **The scanner is its own full-screen `<dialog>` on `/lookup`**, not the bottom sheet, and the
    page is the one place the scanner script loads. "Scan" is a big button on home and a link
    ("Add by scanning") on `/bottles`, both going to `/lookup?scan=1`, which opens the camera on
    load (and says why if it cannot). There is no scan button inside the add-bottle sheet: a
    barcode is not the P code the sheet asks for.
34. **After a barcode is learned the result offers "+ Add bottle"** instead of opening the form by
    itself (section 7.2 said the form opens): the saved shade and its button are on screen, one tap
    away, and nothing else happens uninvited. The add-bottle sheet started from the lookup posts
    `ctx=lookup` and its result replaces the lookup result.
35. **The P-code learning hook is in the `create_bottle` route** (`identifiers.learn_printed`, in
    one transaction with the insert), not in `bottles.add`, and runs on create only, not on edit.
    A conflict (the code points at another shade) keeps the old mapping and saves the bottle; the
    notice "P259 was Spirit Fingers before" is shown above the bottles on the shade page, or in the
    "Added" block on the lookup page, because the sheet has already closed by then. A code that
    does not look like a P number is kept on the bottle and not learned.
36. **The home search is not the resolver.** It stays a name search and, for a query that is all
    digits or looks like a P code, adds a link "Look up “259” as a code" to `/lookup?q=259`, where
    the resolver runs. Typing a number into the lookup field resolves it as 7.2 says.
37. **A P-code suggestion shows a picker, not ordinary name results** (section 7.2 said "underneath,
    ordinary name search results"): the query is the code, which a name search would never match,
    so "Not that one? Pick the shade" is the same typeahead as `unknown_printed` (`ctx=learn`,
    `kind=printed`; a row opens the add-bottle sheet with the code). A typed name still gives rows.
38. **The trimmed fixture, like the real feed, has no barcodes** (they exist only in per-product
    JSON, which v1 never fetches). "Nothing is ever seeded from catalog data" is tested by syncing
    synthetic products whose variants carry a `barcode` and checking `shade_identifier` stays empty.
39. **More templates than PLAN.md lists** (stage 5): `_learn_picker.html`, `_lookup_added.html`,
    and `_shade_row_body.html` (the inside of a shade row, shared by the link row and the learn
    button row of `_shade_row.html`). `/healthz` reports `schema` 3.
40. **A headless smoke test of the scanner** lives in `tests/e2e/scanner_smoke.py` and is not
    collected by pytest (it needs Chromium and a server). It decodes a generated UPC-A image through
    the photo input and through Chromium's fake camera, with `BarcodeDetector` removed so zxing-wasm
    does the work as on an iPhone. How to run it is in its docstring and the README.

41. **The look follows docs/VISUAL.md; where this pass chose differently, it is recorded here.**
    The top bar is gone for a bottom tab bar of five tabs (the old deviation 31, which added
    Bottles and Wishlist to the top bar, is superseded). Sign out moved to the Home footer.
    Tab labels are 11 px (VISUAL.md says caption size, 13 px: five labels at 13 px leave no air on
    a 390 pt screen). (Superseded by the swatch-book overhaul: no webfont, the UI is SF Pro through `system-ui`;
    see docs/advice/fable-swatch-book-2026-10-25.md until VISUAL.md is rewritten.)
42. **Presentation copy changed, behaviour did not.** Middle dots, spaced dashes and `+` prefixes
    are gone from copy ("Added Spirit Fingers with P259.", "New barcode 0810170284120. Which shade
    is it?"); "owned ×2" is the pill "Owned ×2"; the heart toggle is an icon with `aria-pressed` and
    the label "Wishlist" in both states (the old "♥ On wishlist" does not fit a third of the row); the
    wishlist summary is a sentence ("8 shades, $120.00. 3 are in stock now for $44.50."); the home
    wishlist number no longer carries the total. Tests that asserted those strings were updated to
    the new ones; none was weakened.
43. **The thumbnail crops are 3:4** (48 by 64 for rows, 72 by 96 on the Home shelf, 36 by 48 in
    the bottle groups; gallery images 480 by 640): `thumb(url, 96, 128)` for a 2x row, 3x at
    144 by 192. VISUAL.md's example of 144 by 240 is a 3:5 crop that does not match the 48 by 64
    box. Shade pages show finish, colour and collection as chips; rows show them as words.
44. **The level chips of `/bottles` ride along out of band** (`_bottle_filters.html`): the old
    chips sat outside the swapped list, so the highlighted one went stale after the first tap.
45. **A shade with no bottle shows "I have this", one with bottles "Add bottle"** (as before), both
    with a plus icon. The "Owned ×N" pill is part of `#shade-actions`, so every bottle fragment
    keeps it current through the out-of-band swap.
46. **Page titles use a vertical bar** ("Shades | Polished"), not a middle dot.
47. **The sheet's first focus goes to its heading** (`tabindex="-1" autofocus`), not to the first
    radio, so no focus ring appears on a tap. A sheet has no drag-to-dismiss: Cancel, the scrim and
    Esc close it, and the grabber is decoration for now.
48. **A layer swap parks one layer on `ord = count + 1`, not `ord = 0`** (stage 7): `stack_layer.ord` has
    `check (ord >= 1)` (4.3), so 0 is not storable. `stacks.move` sets the moved layer to `count + 1`,
    the neighbour to the moved layer's `ord`, then the moved layer to the neighbour's. Remove and
    over-black renumber one row at a time, in the order that avoids the unique `(stack_id, ord)`.
49. **Saved stacks are ordered by `updated_at` with millisecond precision** (stage 7): `stacks.save`
    writes `strftime('%Y-%m-%dT%H:%M:%fZ')`. "Same as last" and "Copy from…" sort on it, with the
    stack id as tiebreak.
50. **A draft copied from a saved slot also copies the stack name** (stage 7), so editing a named
    swatch keeps its name unless the form changes it.
51. **The ring is CSS only, with generated position rules** (stage 6): `.slot-pos-K` (K = 1..40) sets the
    index and `.ring-n-N` (N = 1..40) the slot count and the width of one wedge; the angle is
    `calc(360deg / var(--n) * var(--i))` and no element carries a style attribute (CSP). The tip
    pictures are not the hit areas: the button over each tip is clipped to a wedge between two rays
    from the hub (`clip-path`), so neighbouring hit areas touch and never overlap, which a rotated
    rectangle cannot do on a ring. At 20 slots a wedge averages 42.8pt wide (measured) and 64pt
    deep; above about 24 slots it is narrower than 42pt (the ring has a fixed 136px radius), and
    the list below is the roomier way in.
52. **Empty tips carry their number upright; filled tips carry none.** The number sits in the tip of an
    empty slot (counter-rotated); a filled tip shows the picture, and its number is in the list below
    and in the button's accessible name.
53. **Out-of-band swaps use `div`s, not `li`s.** The ring is `div.slot` and the list is `div#slot-list`,
    because HTML parsers drop a bare `li` at the top of an HTMX response. `_slot_swap.html` swaps the
    tile (`#slot-N`), the list and `#hub-count`.
54. **Confirmed actions answer with `HX-Redirect`.** Archive, "New tag URL" and "Take the tag" carry
    `hx-confirm`, so they are `hx-post` buttons; for an HTMX request the route answers 200 with
    `HX-Redirect` (a swapped-in 302 target would land in the wrong element), and a plain form post still
    gets the 302 of 13.5. `GET /wheels/{id}/qr.svg` also answers HEAD.
55. **Wheel create is inline, not a sheet,** and a failed create re-renders the list with 422. The list
    shows "N of M swatched" with a mini ring of dots (filled in accent, empty in `--line`), archived
    wheels behind a row at the bottom (`/wheels?archived=1`); the rename form lives in the "This wheel"
    group under the list.
56. **`not_found.html` takes an optional message, button and tab,** so an unknown wheel says so and
    offers "See your wheels". Without them it is the shade page as before.
57. **The builder's context key `oob` was split in two** (stage 7). `layers_context` passes
    `layers_oob`, which only `_stack_layers.html` reads (the live summary, the Save button and the reset
    results ride along out of band); `oob` stays the flag of `_slot_swap.html`. Opening a draft merges both
    dicts, and with one name the sheet's own layer list would have rendered its summary out of band.
58. **`POST /stacks/{id}/layers/{lid}/coats` took `Literal[-1, 1]`, which rejected every form value**
    (`"1"` is a string; the route answered 422 for all of them). `delta` is now an `int` checked against
    -1 and 1 in the route (422 otherwise). The domain layer was not touched.
59. **`/search?ctx=stack` renders `_picker_results.html` with `{"picker": ...}`**, not with the dict as
    the context, so the sheet (`picker_ctx`), the layer responses (`picker`, out of band into
    `#picker-results`) and the search route share one template.
60. **The results sit outside the search form.** `#picker-form` holds the search field and the Owned,
    Toppers and All radios (`hx-trigger="input delay:200ms, search, submit"`, `hx-sync="this:replace"`);
    `#picker-results` is a sibling that carries `hx-target="#stack-layers"` and `hx-include="#picker-form"`
    for its rows. Inside the form the rows would inherit the form's `hx-sync` and a search request could
    abort an in-flight append whose server side had already happened.
61. **More partials than PLAN.md lists:** `_stack_parts.html` (macros for the summary line and the Save
    button, which exist both in the sheet and as out-of-band replacements). The Save button sits in the
    sticky footer and belongs to `#save-form` by its `form` attribute, so the name and note form can
    stay in the scrolling part. The sheet is `div.builder`, not a form, because the search form and the save form sit side by side in it.
62. **No scan button in the builder.** VISUAL 6 draws a camera in the search field; the lookup flow
    ends in "Add bottle", not in a layer, so a link there would leave the builder with nowhere to
    return to. A P code typed into the field is resolved (section 7.2) and shows as a suggestion row.
63. **Layer rows are more compact than VISUAL 6 draws them:** the mini tip spans the name line and the
    controls line (44pt tall), so a row is about 80pt and three layers leave room for the results on
    390x844. A layer with more than one coat also says "2 coats" at the trailing edge of its name. Up and
    down are 24pt arrow icons in 44pt buttons; a missing up (first row) or down (last row) is an empty
    placeholder of the same width, so the others do not jump. Coats `-` is disabled at 1 and `+` at 5.
64. **A short viewport (`max-height: 560px`, which is what an open keyboard leaves) compacts the sheet:**
    no grabber, the summary on two lines, the layers in a scroll area of about 150pt and the footer no
    longer sticky, so the search field and the first results stay in view. The live summary is in the
    sticky head in every case, so the whole stack stays readable while the layers scroll.
65. **Keyboard handling on the results:** `mousedown` on a result row is cancelled while the search field has
    focus (the click still fires), so a tap does not drop the keyboard; after a layer was added the
    server sends `HX-Trigger: pickerReset`, `sheet.js` empties the field, puts focus back only if it had
    it when the request left, and scrolls the new layer (`is-new`) into view. Nothing is focused when the
    field was not, because iOS ignores focus outside a gesture. Whether the keyboard really stays up on
    a tap is the manual check of PLAN stage 7.
66. **Cancel and the save error.** Cancel in the header discards the draft without a confirmation (the
    spec's word); a 404 or 409 from a stale sheet (`htmx:responseError`) shows "This swatch changed
    somewhere else" in `#builder-status`. A failed save (no layer, a date that is not YYYY-MM-DD) is a
    422 retargeted at `#save-error` in the footer. Save is disabled while the draft has no layer.
67. **PLAN stage 7's acceptance `grep -c 'slot hl'` is stale:** the highlighted tile's class list is
    `slot slot-pos-N ring-n-M is-filled is-hl`; the check is `grep -c is-hl`.
68. **Purchase history is a view of `bottle`, no new table or migration.** `bottles.history(conn)` returns
    years -> months -> rows (newest first); `group_history` is the pure part. A bottle is dated by
    `bought_on`, or by the date part of `created_at` (UTC, as stored) when that is empty, and such a row
    says "Added 25 Oct 2026" where the others say "Bought ...". Totals add `price_paid_cents`; a bottle
    without a price is counted and left out of the sum, and the heading says "2 without a price". Archived
    and empty bottles are included (rows say "archived" or "empty"). `/bottles` and `/bottles/history`
    share a Collection | History switch (`_bottle_views.html`, links styled as a segmented control).
69. **"I bought these" is `wishlist.mark_bought(conn, [(item_id, price_cents)], bought_on)`** inside
    `db.atomic`: it checks every item first (`LookupError` for an unknown one, `ValueError` for none, a
    repeat or a bad date), then adds a full bottle and removes the item, so a failure leaves both tables as
    they were. The route reads the raw form (`await request.form()`) because the price fields are named
    `price-<id>`; unknown ids are 404 before validation, a bad price or date or nothing ticked is a 422
    that re-renders the sheet with what was typed. The sheet's button sits under the checkout box and
    includes its `max_priority` radios, so the rows that start ticked are the buyable ones the box
    counts; the prices start at the shade's list price and the date at today in `POLISHED_TIMEZONE`.
    The confirmation ("3 bottles added. See them in History.") is part of `#wishlist`, so it goes with
    the next change to the list. `sheet.js` is now loaded on the wishlist page.
70. **The shade page splits its bottles:** "Bottles" for owned ones and a quieter "Past bottles" for
    archived and empty ones (before, they shared one list). A card changed in place stays where it is
    until the page is loaded again. `is_owned` is a Jinja test (`owned_bottle`) for the split.
71. **Swatch photo per shade** (visual polish pass, advisor review 2026-10-25, `docs/advice/fable-review-2026-10-25.md`):
    migration `005_swatch_image.sql`, `parse.swatch_image_url(images, title="")` and a sync backfill (4.3, 5.2).
    Tips, mini tips, layer tips and the ring's bands use `swatch_image_url or hero_image_url` through the
    `tip_img` macro in `_tip_img.html`; the hero fallback gets class `is-bottle` (crop to the glass). The
    heuristic differs from the review in three ways: whole words (so `InsideJob` is not a "side" shot),
    the shade's own title words are ignored (so `BottleService` files qualify), and a fourth rank for
    older products whose files are numbered page shots (`pdp`, `layer`, position 2 or later), which lifts
    coverage from 306 to 351 of 372. `wheels.slot_grid`/`slot_tile` layers and `stacks.layers` carry the
    column. The picker, shade rows, shelf and wishlist keep the bottle shot on purpose: they identify a bottle.
    **Superseded by 77:** no tip shows a photo any more; `swatch_image_url` is only the colour's source.
72. **Bottle card:** the four-segment level control left the card; it shows one pill ("Half ›") that opens the
    edit sheet, which holds the segmented control. The `Edit` text button went (the pill is the way in); the
    title is the P code, else "Bought 12 Mar 2026", else "Bottle", and "No P code." moves to the caption with
    the price ("Paid $13.00."). `POST /bottles/<id>/state` stays, unused by the card. **Superseded by 81.**
73. **Owned pill on the shade page** lives in the subhead after the price (`_owned_pill.html`, a span that
    bottle fragments replace out of band), the shade-page button is always "Add bottle", and "In stock" is
    not shown (silence is in stock, as in the rows).
74. **Builder layer rows:** no "N coats" text, the red remove icon is `--ink-2` (red only while pressed), and
    the move arrows show only from 3 layers (`.rail:not(:has(li:nth-child(3)))`). The sheet title is
    "Slot 12" with the wheel name as the caption.
75. **Wishlist rows:** the note input sits behind an "Add a note" disclosure (open when a note exists) and
    Remove is `--ink-2`. The checkout "I bought these" sheet puts a "$" inside each price field.
76. **Smaller presentation changes:** wheel page "Archive wheel" is accent text, not red; the Owned pill is
    not shown in picker rows under the Owned filter; the tag page shows "Open the wheel" under the intro;
    the lookup page has one primary (the photo option is a text button); the slot list shows a date only
    when it differs from the row above; the Bottles empty state offers "Add a bottle" (to `/lookup`); the
    offline and signed-out marks use `apple-touch-icon.png`; the segmented thumb is lighter (2px border,
    `0 1px 2px` shadow); the builder search focus ring is inset.
77. **Tips are generated SVG, not photos** (Jan, 2026-10-25: bottles, then macro photos, "look extremely weird"
    in a nail tip). Migration `006_swatch_colour.sql` (`swatch_hex`, `swatch_hex2`, `swatch_hex_src`,
    `swatch_override_hex`), `catalog/colour.py` (5.5), `tips.py` and `routes/tips.py` (9). The `is-bottle`
    crop, the `tip-bands` (a composite stack drawing already shows every layer) and `swatch_image_url or
    hero_image_url` in the `tip_img` macro are gone; `_tip_img.html` now has `shade_tip` (one shade, for
    mini tips and builder layers) and `stack_tip` (the ring). The wheel and stack queries select
    `tips.TIP_FIELDS` (kind, is_topper, the colours, the finish tags) instead of the image URLs.
78. **The colour step runs inside the sync's lock after the run row is closed,** so a run shows "ok" while
    the first colour read (about 7 minutes for 372 shades at 0.5 s apart) is still going; later runs read
    only new shades and changed photos. `sync --from-files` also reads colours from the CDN (a CDN, not the
    store) unless `--no-colours` is given, and the unit tests inject `httpx.MockTransport` (`SyncRunner(colour_transport=...)`). A topper's
    first colour is the livelier cluster, not the base it was photographed over.
79. **Tip colour override instead of a photo picker:** the shade page has a colour input, not an image sheet;
    `swatch_override_hex` replaces `swatch_hex` and drops `swatch_hex2`; the sync never writes it. Effective
    colour order: override, `swatch_hex`, neutral (`#c9bfc0`).
80. **The swatch book, run 1: tokens, controls, tips, ring** (Jan: "a bit ugly ... it should be beautiful",
    `docs/advice/fable-swatch-book-2026-10-25.md`; VISUAL.md is rewritten after run 2 and its colours,
    Fraunces and pill controls no longer apply). What changed and where it departs from the advice:
    - No webfont: Fraunces, its OFL file, the preload, the precache entry, the `VERSIONS.txt` entry,
      `scripts/make_fonts.sh` and the Dockerfile's font self-check are gone (the self-check now asserts
      `static/icons/ui.svg`). The type scale is roles (large title 34, sheet and shade title 28,
      section 22, headline and buttons 17, subhead 15, footnote 13, caption 12, hub number 44); the
      earlier 14 and 19 px sizes went into the scale. Tab labels are 12 (the advice) and no longer 11.
    - Tokens are the advice's table in hex; `--heart-text` was dropped because nothing needs pink text:
      the heart icon is the only pink (the wishlist counts on Home and in the wishlist group heads are ink).
      The prefers-contrast block still overrides `--line`, `--line-2` and `--mat` for both schemes.
    - One filled action per view is `--primary`; the segmented control and the on chip are `--primary`
      with `--primary-on` text; stepper, chips, inputs and the secondary button follow the advice. The
      shade page's wishlist control is the heart icon button (`.btn-heart`, 50 pt, `--fill`, the heart
      pink and filled when on) beside "Add bottle"; its accessible name carries the state.
    - Tips replace bottle photos in every list (`_tip.html`, sizes s 28x46, m 40x66, l 56x92, xl 72x118).
      The shade rows, the Home shelf, the bottle groups, the history rows, the wishlist rows, the bought
      sheet and the builder's picker and layers use the shade's tip; the wheel page's slot list and the
      builder's "Copy from" list use the stack's composite tip. `.mini-tips` is gone. The bottle photo
      stays on the shade page strip and the lookup result (`ctx == 'result'`).
    - The ring has a 150px radius at full width, a hairline circle, tips 38x62, empties without foil,
      and a hub that holds only the number and "of N". `_slot_swap.html` swaps `#hub-name` (the number)
      and `#hub-count` ("of N"); rename no longer touches the hub.
    - Two defects found by the screenshots are fixed here: the number on an empty tip no longer widens
      the page on a 12-slot ring (a 7px horizontal scroll that pushed the tab bar off the screen), and the
      hidden file input of the lookup page no longer sits past the right edge (same symptom, 408px).
    - Left for run 2 (advice section 4): the Home restructure, the wheel list's mini rings, lookup
      camera-first, the shade page's tip beside the title. The level glyph, Archive in the bottle sheet, the
      wishlist head and rows and the builder's composite head are run 2a (81).

81. **Run 2a: Bottles, Wishlist and the builder sheet** (advice section 3; the screens only, Home, Wheels,
    shade detail and lookup are run 2b). Where it departs from the advice or the brief:
    - **Bottle rows** are plain rows of one grouped list per shade (`_bottle_card.html`, still the one
      partial the shade page uses): P code or "No P code" in `--ink-2`, a footnote "Bought 21 Jul 2026,
      $15.50" (or "Paid $15.50"; "Archived." leads it for an archived bottle), then "Opened ..." and the
      notes. The whole row is the button that opens the edit sheet; the pill, the red-free "Archive" text
      and the "Bought 18 May 2026" title are gone (72 is superseded).
    - **The level glyph** (`_level_glyph.html`) is an inline SVG bottle, 20x35, with the liquid drawn as a
      path filled to 100 / 50 / 25 / 0 percent in the shade's colour (`tip_hex`). The colour is a `fill`
      attribute, not a style, so the CSP has nothing to block and no per-shade CSS or extra route exists. The
      outline and cap are `currentColor` (`--ink-3`); the word beside it (Full, Half, Low, Empty) is `--ink-2`
      in every state (the amber "Low" went: the glyph is the colour).
    - **Archive moved into the edit sheet**, a quiet text action beside "Delete this entry" (red, because it
      destroys); "Restore this bottle" for an archived one. The route is unchanged but now closes the sheet,
      and on `/bottles` (`ctx=list`) it answers with an empty body so the row leaves the list that is on
      screen (a group with no row left is hidden by `:has()`); on the shade page (`ctx=shade`) the card stays,
      marked "Archived". The counts line is not recomputed until the next load.
    - **The level filter** is one row of five outlined chips (`.chip-row`, flex with wrap, no scroller). "Archived"
      left the chips for a text toggle, "Show archived" / "Hide archived", at the right of the count line
      ("Archived bottles" while it is on); both ride along out of band with the chips.
    - **Wishlist head** is the advice's short head: the checkout box (one line, footnote, button, "Copy list" and
      "I bought these" side by side, the include segmented) on the board; the sentence summary, the "Include"
      label, the hint and the plain names list are gone (the names stay in a hidden textarea for Copy list).
      The total is of what the link carries, so the wishlist's grand total (items not in stock) is no longer
      shown. "I bought these" moved into the cart box, so it is swapped with it and reads the same filter.
    - **Wishlist rows** are a grid: tip, title (a stretched link to the shade), price at the trailing edge, a
      footnote line for status and "Owned ×N" (plain text, no pill), the note as a footnote button ("Add a
      note" in ink 600 when empty) and a native `<select>` for the priority ("Want most" with a chevron).
      The note button opens the row's sheet (`_wishlist_sheet.html`: note, "Remove from wishlist" in red, Save
      note); Remove left the row. The menu posts to a new `POST /wishlist/{id}/priority` because FastAPI reads
      an empty form field as missing, so "priority alone, keep the note" cannot share `POST /wishlist/{id}`
      with "the sheet clears the note".
    - **Builder head** is the stack's composite tip (72x118) beside "Slot 3", the wheel name as a caption and
      Cancel, the summary under them as body text (17, weight 400, two lines at most; the layers list shows
      all of them). "Resumed your draft." is a footnote in the head, not a notice in the layers.
      `sheet_context` passes `resumed` instead of a notice. The tip is `#stack-tip`; every layer edit appends the
      new `/tips/stack/{id}.svg?v=<revision>` over the old one out of band (`beforeend:#stack-tip`, a blank
      shape when the last layer went), `sheet.js` fades it in on `load` (an opacity transition, so it holds
      under reduced motion) and then drops the pictures under it, so a slow connection never shows an empty
      nail. The shortcut chips wrap (`flex-wrap`, 10px padding) instead of scrolling.
    - Small: `ui.svg` has a `chevron-down`; `.sheet-danger` is `.sheet-quiet` (it now holds Archive and Remove
      as well as the destructive actions); the sheet's subtitle and note no longer balance their wrap.
    - For 2b: the shade page's bottle list is the same partial, so it already has rows, glyphs and "Archive
      this bottle" in the sheet; its `<h2>Bottles</h2>` section titles and its "Past bottles" heading are
      untouched. `.group-head` (tip, name, link) is the bottle list's shade head and could serve the shade
      list. `.sheet-quiet` is the place for a sheet's secondary actions.

82. **Run 2b: Home, Wheels, wheel page, shade detail, shade rows, filter panel, lookup** (advice section 3; with
    this the swatch-book overhaul is complete and VISUAL.md is rewritten from the built result). Where it departs
    from the advice or the brief:
    - **Home** has no "last opened" wheel: the database does not record opens and a read should not write, so it
      shows the wheel whose saved or draft stack was updated last (`wheels.most_recent`, no migration). The
      ring is the wheel page's own CSS at 200px; the whole block links to the wheel. The icon tile has the
      `--mat` ring so plum does not vanish into plum in dark. The stat block is one line of three links ("9
      bottles, 8 shades, 6 wished", hidden while all three are zero), the big "Scan a bottle" button left (the
      camera in the search field and the Bottles tab remain) except in the no-bottles empty state, which is one
      line and that button. "Add a shade by hand", "Catalog sync", "Learned codes" and Sign out moved to a new
      `GET /more`; Home keeps "More ›". The shelf heading stays "Recent bottles" (it is the latest added, not
      what she wore). Tests that read the old stat block or "Signed in as" on `/` now read the line and `/more`.
    - **Wheels list:** the "+" is a `<details>` summary in the title row (no JavaScript); rows show a 72px ring of
      the wheel's real tips and "13 of 20, 2 drafts" ("swatched" is dropped; the wheel page still says it in
      its label). The empty state is the unpainted ring (12 tips), a line and the form.
    - **Wheel page:** ring, tips and hub were already as the advice says (150px radius, 38 by 62 tips, hairline
      rail, hub number and "of N"); a tip is now capped at its pitch (`min()` in `.tip`), a no-op up to 24
      slots. "This wheel" is a quiet row at the foot; **Rename moved into a sheet** (`GET /wheels/{id}/rename`)
      because an inline field cannot sit in a row of three actions; the old "Renamed." status is gone, the
      sheet closes and the title changes. The slot list kept the number before the tip (as in the advice's
      wireframe).
    - **Shade rows** put the name and price on one line, the heart inline after the name, the status word first
      in the subhead and "×N" under the price; the "Owned ×N" pill and the row-flags line are gone. In `/search`
      results and the learn picker the rows are the same.
    - **Shade detail:** tip-l beside the title; price, "Owned ×N" (plain text now, no pill) and the status on one
      line; Finish, Colour and Collections are a quiet list (label over outlined chips, not three section
      titles); "Swatched on" rows start with the stack's composite tip (`_detail_context` loads the layers);
      the Tip colour card is a closed disclosure at the foot (supersedes 79's card layout, not its route).
    - **Filter panel:** shut on load even with filters active (it covered the results when Home's "Toppers"
      opened it; the badge counts the filters; supersedes the open-when-filtered rule), no shadow in dark (a 1px
      ring), and a sticky bar with "Clear all" and one filled "Show N shades" that closes the panel
      (`[data-close-details]` in `chrome.js`; `_filter_show.html` is swapped out of band with the count).
    - **Lookup:** the scanner is no longer full screen. The `<dialog id="scanner">` is non-modal, laid over a 4:3
      viewfinder at the top of the page, so the camera is the first thing and the field is below it; `scanner.js`
      calls `show()` instead of `showModal()`, handles Esc itself, and the status line is the caption under the
      viewfinder. `body:has(dialog[open])` scroll lock is now `dialog.sheet`. The result card
      (`_result_card.html`) puts the bottle photo (72 by 96) beside the shade's tip-l; both smoke tests are
      unchanged and pass. Supersedes 33's "full-screen".
    - Wheel list "mini ring of dots" and the "This wheel" group (55) are superseded.

83. **The release sheet** (Jan: the shop's dates are wrong for old shades and it does not list every shade;
    the sheet is Holo Taco's own "Official Simply Holo Taco nail polish release list"). Section 5.6 has the
    design. Where it goes beyond what was asked, or departs from it:
    - **Table rebuild, not a side column.** `shade.source` gets `'sheet'` (migration 007 rebuilds the table,
      4.3) rather than putting sheet-only shades under `'manual'` plus a flag: `manual` means "typed by the
      household" in the UI and in `status()`, and a sheet shade must not look like that. The cost is a
      rebuild, made safe by foreign keys off in `migrate.py` and a before and after `foreign_key_check` per
      file; every other migration is unchanged by it.
    - **Only `Retired` retires.** The sheet's Retired? column holds 143 `Retired` and 6 `Seasonal` (149 non-empty,
      the number in the brief). `Seasonal` (Glow In The Dark Taco, Aqua Glow In The Dark Taco, four of the
      Declassified Tacos Set [003]) is a seasonal release that can return, so it is not retired.
    - **No aliases were needed.** After normalising ™, accents, case and punctuation, all 364 sheet names that
      the shop lists match; `ALIASES` exists and is empty, with a test that proves the mechanism.
    - **The fetch is two HTTP requests.** Google redirects the export URL (307) to googleusercontent.com; the
      one logical fetch follows it, to Google hosts only.
    - **`--from-files` stays offline.** It skips the sheet unless `--sheet FILE.csv` is given, so a local run
      never reaches Google by surprise.
    - **A sheet-only shade says "Not in the shop" even when retired** (nine of the ten are). It is in none of
      the Status filters, like a shade the shop dropped. Its retirement shows as ", retired" on the release line.
    - **Two sorts about dates.** "Release date, newest first" is new; "Newest" is relabelled "Recently listed"
      because it still reads the shop's `published_at`, which is the date the sheet corrects. Home's "New and
      in stock" link still uses it (not changed; `sort=released` would suit it better).
    - **Guards** that were not asked for: more than 40 new sheet-only shades in a run, or fewer than 300 rows,
      stops the step with nothing written; a failed step is a warning and the next run tries again.
    - **A merge folds the sheet-only row into the shop shade** (moving bottles, layers, codes, aliases and the
      wish) instead of converting the row in place, so one code path serves a shade that appears in the same
      sync, a later one, and a duplicate made by hand.
    - Shop and sheet are not one transaction: between a shop run that adds a shade and the sheet step that
      merges it the shade exists twice, for seconds, or until the next run when the sheet is down.

84. **Fuzzy search, deleting a wheel, and observable browser flows** (Jan, 2026-10-26: "I got mixed up with
    `Holo Magnetic Taco` and `Magnetic Taco`"; "I want to Delete one fully ... of course it should ask for
    confirmation"; "add/create some test flows that you can observe and validate"). Sections 6 and 9 have the
    design; where this goes beyond what was asked, or departs from it:
    - **Search ranking is in Python (`search.py`), not SQL.** `list_shades` asks `search.rank` for the matching ids
      in order when the query has words, applies the other filters in SQL and keeps the intersection; without
      words nothing changed. The tiers, the edit budget (1 for 4 to 7 letters, 2 from 8, a swap is one edit) and
      the missing-space rule are in section 6. Trigram similarity was not used: edit distance over words is exact
      and explainable at 372 shades.
    - **Ownership no longer outranks relevance.** The home search and the picker used to put owned, then wishlisted,
      shades first; with a typed query that would have put an owned "Holo Magnetic Taco" above "Magnetic Taco" for
      the query "magnetic taco", which is the confusion this fixes. It is now a tie-break after tier, edits and
      title length (an empty picker query still lists owned first). Three tests changed with the new order
      ("Beta Pink" before "Alpha Pink": shorter first) and with the `<mark>` split of titles in the HTML.
    - **Speed** on the full local snapshot (372 shades, 526 products): 0.8 to 1.1 ms per `shades.search` call
      warm, 1.1 to 2.3 ms with cold caches, for the cases below and for one-letter queries (361 matches).
    - **Deleting a wheel is a new route pair, not a changed archive.** Archive is unchanged and stays the quiet
      way to put a wheel away. The confirmation is a sheet that posts `confirm=yes`; typing the wheel's name was
      considered and not done (the sheet already names the wheel and counts its swatches). The sheet mentions the
      tag only when the wheel has swatches.
    - **No migration.** The foreign keys already cascade slots with the wheel and layers with their stack; the
      stacks themselves are deleted in code, in one transaction.
    - **Flows (`tests/e2e/run_flows.py`, `tests/e2e/flows/`)** are not part of `pytest -q`. One entry point
      starts the app on a fresh copy of a database seeded by `flows/seed.py` (the trimmed fixture feed, the trimmed
      release sheet, eight more shades the flows search for, a painted tip colour per shade; no network) for every
      flow, device and scheme, so no run sees another's data. Devices are Chromium with Playwright's "iPhone 15" and
      "iPad Pro 11" profiles (touch) and a 1440×900 desktop (mouse), each in light and dark (WebKit is not
      installed). Every flow is a list of named steps (`harness.Trace.step`); a step ends with a screenshot and
      these audits: console errors and warnings, failed requests (a request the page cancelled itself is
      ignored), 4xx and 5xx (a flow that provokes a 404 says so with `allow_status`), horizontal overflow, and on
      touch devices interactive elements under 44 by 44 points (a stretched link or padded hit area is measured by
      hit-testing, and inline links in a sentence are exempt). A failing step stops its flow and the report
      (`index.html`, one row per flow × device × scheme with the step screenshots and the failure text, plus
      `summary.json`) shows where; the exit status is 1 when any step failed. Flows: search (the ranking and typo
      cases), add-bottle, bottle-level, wishlist (priority, "I bought these"), wheel-build (a three-layer swatch on
      the ring and in "Swatched on"), wheel-delete, scan-photo, browse-filters, history, and a tour of every tab.
      Selectors are roles, labels and text; the only ids used are the ones htmx targets. The two older smoke tests
      are unchanged apart from sharing `flows/media.py`.
    - **Screenshots are taken through the DevTools protocol.** Playwright's own `page.screenshot()` hides the text
      caret by setting `style` on inputs and leaves empty `style` attributes behind; htmx then copies them during a
      swap and the browser logs a CSP violation (`style-src-attr`) that no real user has. The flows capture with
      `Page.captureScreenshot` instead.
    - **Found while writing the flows:** after a swatch is saved or removed the ring's `aria-label`
      ("Holos, 0 of 20 swatched") was not refreshed, only the hub's count was, so a screen reader heard the old
      number until the page was reloaded. Fixed in item 85.

85. **v3 run 1, "light and letters"** (`docs/advice/fable-v3-web-2026-10-26.md` sections 2, 4.1 to 4.3 and 4.6;
    VISUAL.md is rewritten for it). The screens, tokens and components of run 1 only; the shells (run 2) and the
    Home shelf and wear (run 3) are not built. What was built and where it departs from the spec:
    - **Tokens** are the spec's table (warm light neutrals, dark unchanged) plus `--velvet`, `--shadow-ink`,
      `--rim` and `--material-light`; the `theme-color` metas and the manifest's light colour follow `--bg`
      (`#f7f3f2`).
    - **Fraunces** is vendored under `static/vendor/fraunces/` (Fontsource 5.3.0, from the npm tarball, hashes in
      `VERSIONS.txt`), instanced with fonttools to `wght` 500 to 700 and `opsz` 72 to 144 and subset to Latin
      (52 KB, preloaded and precached) and Latin-ext (29 KB, by `unicode-range`). It is used at 600 with `opsz`
      144 in four roles: the greeting, the shade title, the wheel name (34 on the wheel page, 22 in the list) and
      the hub number (56). A test fails if another selector takes `--display`. The fallback face is Georgia at a
      measured `size-adjust` of 77.4 percent, not the guessed value the build started with. The Home greeting's
      mark moved from the end of the greeting's row to the date's row, because "Good afternoon, Georgia" is 322px at
      34px and the mark left 269px; now a seven-letter name fits one line at 390 for every greeting.
    - **The lit tip** is the spec's `.tip > .tip-face` structure at every tip site (`_tip.html`, the builder head,
      the ring slots, the Home and Wheels rings), with the sizes of 2.4 for the phone shell (`tip-l` 72 by 118 and
      `tip-xl` 96 by 158 replace the older 56 by 92 and 72 by 118). The ring's slots are lit with the light turned
      back against the slot's angle; the small rings (200px and 72px) keep only the edge and a contact shadow. The
      two `tips.py` tweaks are in (dome edge .18, highlight at (66, 30)) and `tips.DRAWING_VERSION` joins the hash
      behind the image URLs: not in the spec, but those URLs are cached for good, so without it a browser would
      keep showing the old drawing under the new light. A ring slot's keyboard focus is the foil ring (spec 2.6)
      with the ink outline kept beyond it, since pale foil alone does not carry 3:1.
    - **The per-tip blur** (the contact shadow is a 4px blur on a pseudo-element) was measured on the full
      372-row Shades list (10 "Load more" taps) on Chromium's iPhone 15 profile with a 4x CPU throttle: 60 fps
      throughout, 0.0 to 0.2 percent of frames over 20ms, no difference with the blur, the soft-light blend or the
      shadow removed. The pre-blurred gradient fallback was not needed. WebKit is not installed here, so real iOS
      Safari is unmeasured.
    - **The level arc** replaces `_level_glyph.html` everywhere (bottle rows, the edit sheet's segments). It is
      ink in both modes; Low and Empty keep their word colour.
    - **Bottle rows and the edit sheet** follow 4.3: the first line is the purchase, the P code trails it at 13px
      `--ink-3`, and the sheet reads Level, Bought on, then More details (Price paid, Opened on, P code, Notes). A
      bottle with no purchase facts and no code reads "Added <date>" so its row is not empty (the spec omits "No P
      code" and says nothing for this case); a bottle with a code and no purchase facts shows the code alone.
    - **The date field** is the spec's overlay over a transparent native input, with words, the presets and `max`
      = today. It is on every date input: Bought on and Opened on (bottle sheet), Bought on (the bought sheet) and
      Swatched on (the builder). The server refuses a date after today in the household's time zone for all four
      (bottles, `wishlist/bought` and `stacks.save`, which raises `FutureDate`); a browser already holds a future
      value back through `max`, so the message is the back stop for a request that did not come from the page.
      The preset buttons are not wrapped in a labelled group: a group named "Quick dates for bought on" matched a
      lookup by the label "Bought on", which made the field ambiguous to assistive tech and to the flows.
    - **The shade head** is the tip at `tip-xl` beside the title on a plate (`--surface` in light, `--velvet` in
      dark).
    - **Search marks and no results:** `<mark>` is styled as in 4.6, and both no-result states (the Shades list and
      the typeahead) show a lit unpainted tip, drawn in CSS rather than `nail-tip.svg` (no new asset), with "Try
      fewer letters". The count line "3 matches, closest first", the collection or year hint on near-duplicate
      names, `aria-current` on the first result and `Enter` opening it are not built: they belong with the panel
      shell of run 2.
    - **Icons** `calendar`, `qr`, `trash`, `sparkle`, `sidebar`, `arrow-up-right` are added to `ui.svg`; only
      `calendar` is used so far.
    - **The ring's `aria-label`** (item 84's finding) is fixed: the ring is labelled by `#ring-label`, a visually
      hidden element that `_slot_swap.html` (save, clear, cancel, open a draft) and the rename response swap out of
      band with the hub's number.
    - **`sync --from-files ... --no-colours`** is added: the colour step downloads shade photos from
      `cdn.shopify.com`, so `--from-files` alone was not offline. The README, AGENTS.md and section 5.4 say so;
      the flag makes a run touch no network at all.
    - **Flows** changed only where markup legitimately did: Home's `h1` is the greeting now, not "Polished". New
      steps: the date field's words and presets and the refusal of a future day (add-bottle), "Try fewer letters"
      (search) and the ring's label after a save (wheel-build).

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

No `--proxy-headers` or `--forwarded-allow-ips`: absolute URLs, the Origin check and the secure
cookie come from `PUBLIC_URL` and `AUTH_MODE`, and the login `next=` check compares only the Host
header, which envoy passes through. The init container gets the same `envFrom` as the app, because
settings validation requires the OIDC variables for `migrate` too. Image tags are `edge` and
`sha-<short>` on every push to main, plus `X.Y.Z`, `X.Y`, `X` and `latest` on a release.

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

## 17. API and the native app

The iPhone and iPad app (docs/NATIVE.md) talks to a JSON API under `/api/v1`, in `src/polished/api/`. It reuses the domain modules unchanged and serialises their dicts through the response models in `api/schemas.py`; `spec/api/openapi.yaml` is generated from those models (`scripts/make_api_spec.py`, with `tests/test_api_spec.py` failing on drift) and `spec/api/fixtures/*.json` are recorded responses (and request bodies) from the seeded e2e database plus an invented household (`scripts/make_api_fixtures.py`).

**17.1 Auth.** `/api/v1` accepts only `Authorization: Bearer <token>`; cookies are ignored. A missing, unknown or revoked token is a 401 `{"error":{"code":"unauthorized"}}`, never a redirect. The Origin check skips `/api/v1` (nothing there authenticates by cookie). Tokens are per device, stored as sha256 (`api_token`, migration 008); `last_used_at` moves at most once a minute. Sign-in: the app opens `/auth/app/start?challenge=&device=` in `ASWebAuthenticationSession`; the web session keeps the PKCE challenge through the Pocket ID login; `/auth/app/finish` mints a single-use 60 s code (`app_login_code`, sha256) bound to the user and challenge; `POST /api/v1/auth/exchange` checks TTL, single use and `sha256(verifier) == challenge` (a wrong verifier burns the code) and returns `{token, token_id, user}`. `POST /auth/revoke`, `GET /auth/devices` and `DELETE /auth/devices/{id}` work on the calling user's tokens.

**17.2 Sign-in callback.** The app's sign-in ends at an app-claimed https address, `https://<host of PUBLIC_URL>/auth/app/callback?code=<code>`, never a custom URL scheme: any installed app can register a scheme, and `/auth/app/start` takes the PKCE challenge from a public GET, so a scheme callback would let a hostile app choose the verifier and collect the victim's code (security review of c6a7475, 2026-10-26). iOS hands `ASWebAuthenticationSession` an https redirect only for an address the app has claimed through the domain's own AASA (`webcredentials` with the app ID) and the `webcredentials:` entitlement. The AASA's `applinks` never lists `/auth/*`. `/auth/app/finish` redirects there with `Cache-Control: no-store`. `GET /auth/app/callback` is a public page that never reads, mints or redeems anything, and the access log drops its query. `/auth/app/start` keeps one pending sign-in per session (a new start replaces it), at most 10 minutes old.

**17.3 Dev token and UI-test reset.** Only with `POLISHED_AUTH_MODE=none` (so a loopback bind): `POLISHED_DEV_TOKEN` is accepted as a bearer token as user `dev`, and `POLISHED_TEST_RESET_FROM=<template.db>` registers `POST /__test/reset`, which copies the template over the live DB with SQLite's backup API, from loopback only (404 elsewhere). Settings refuse both variables in oidc mode. Never tunnel a none-mode server.

**17.4 Reads.** Every GET answers `ETag` (hash of the body), honours `If-None-Match` (304) and sends `Cache-Control: private, no-cache` and `Vary: Authorization`; every answer under `/api/v1` carries `X-Polished-Api: 1`. Errors are `{"error":{"code","message","field"?,"fields"?}}`. Shade rows carry the tip recipe (`Tip`: the same `TipShade` and `revision()` the web uses) and `marks` as Unicode-scalar offsets.

**17.5 Universal links.** `GET /.well-known/apple-app-site-association` is public JSON, registered only when `POLISHED_APPLE_TEAM_ID` is set: applinks for `<team>.com.janpuc.polished` on `/w/*` and `/shades/*` (`/shades/new` excluded), and `webcredentials` for the same app ID.

**17.6 Writes.** Every write of NATIVE.md §3 lives under `src/polished/api/` and calls the domain modules; no rule is restated. Bodies are JSON, a PATCH changes only the keys it sends, money is cents, dates may not pass today in the household timezone, and errors carry the web's sentences (`field`, and `fields` when several are wrong). Stack refusals map as in the web: NotADraft 409, StackFull and EmptyStack 422, the not-found kinds 404. Multi-row writes (`/wishlist/bought`, save, wheel delete, bottle create with its learned P code) are single transactions. A write without a Bearer token is a 401 and changes nothing.

**17.7 Wear.** `wear(shade_id, worn_on, created_at)`, unique per shade per day (migration 009), written by `POST /api/v1/wear/{shade_id}` in the household's local date. `src/polished/wear.py` holds the rules (framework-free, shared with the web's Home): the candidates are shades with a bottle that is neither archived nor empty; today's pick is drawn by a generator seeded with the date, weighted by wearings of the previous 30 days (a recent wearing counts for between 0.1 and 1); the shade already worn today is shown instead; "Another" is a random draw excluding the shown shade, with the same weights counting today too. A sheet-shade merge moves wearings to the shop shade.
