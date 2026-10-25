# polished: v1 build plan

Read `DESIGN.md` first; it holds the schema, routes and algorithms this plan builds. Stage
numbers match the "Stage" column of its route tables. One stage is one agent run. Every stage
leaves a runnable app, ends with its acceptance commands passing, and then **stops**: the
orchestrating session reviews and commits it before the next stage starts.

## Rules for every stage

- **Definition of done**, in addition to the stage's own checks: `uv run ruff check`,
  `uv run ruff format --check` and the whole `uv run pytest -q` suite are green (not only the
  new tests); `docs/DESIGN.md` still describes what the code does (a deviation is written into
  its section 14 in the same change); the stage agent commits, stages and pushes nothing; `.env`, databases,
  `research/*.json` and photos stay untracked.
- **Never hit holotaco.com** from tests or acceptance. Tests use `tests/fixtures/` through
  `httpx.MockTransport`; local runs use `sync --from-files`. Stage 1's `conftest.py` blocks
  outbound sockets in tests so a mistake fails loudly.
- **Report format** after each stage: what changed (files), commands run with results, anything
  that deviates from DESIGN.md, manual checks left for Jan.
- **Migrations are append-only**: a stage adds `NNN_name.sql`, never edits an applied one.
- **Local run** (used by the curl checks below; the smoke recipe is stage 1's `README.md`
  section):

  ```sh
  export POLISHED_DB_PATH=$(mktemp -d)/polished.db POLISHED_AUTH_MODE=none \
         POLISHED_PUBLIC_URL=http://localhost:8080 POLISHED_SYNC_ENABLED=false \
         POLISHED_SESSION_SECRET=dev-secret-dev-secret-dev-secret-00
  uv run python -m polished migrate
  uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json   # from stage 2
  (uv run python -m polished serve & echo $! > /tmp/polished.pid); sleep 2
  curl -fsS localhost:8080/healthz
  kill $(cat /tmp/polished.pid)
  ```

  Mutating curls need `-H 'Origin: http://localhost:8080'` (the Origin check; a missing header is
  itself a test: expect 403).

## Stage 1: skeleton, storage, authentication

**Goal:** `python -m polished serve` runs a FastAPI app with `/healthz`, working login (OIDC or
`AUTH_MODE=none`), deny-by-default gate, security headers, a base layout and the catalog schema.

**Create:**
- `pyproject.toml` (name `polished`, version 0.1.0, Python ≥ 3.12; dependencies fastapi,
  uvicorn[standard], jinja2, python-multipart, httpx, authlib, itsdangerous, pydantic-settings,
  tzdata; dev extra pytest, pytest-asyncio, ruff; ruff and pytest config copied from
  serendip's `pyproject.toml`, `testpaths = ["tests"]`), `uv.lock`.
- `src/polished/{__init__,__main__,cli,config,db,migrate,server,web,security,auth}.py`;
  `migrate.py` follows serendip's runner (`schema_version`, one transaction per file, a
  `directory` parameter for tests).
- `src/polished/migrations/001_catalog.sql`: the SQL of DESIGN 4.1, verbatim.
- `src/polished/routes/health.py`; `templates/{base.html,home.html,signed_out.html,
  forbidden.html}` (home is a placeholder until stage 3); `static/css/app.css` (mobile-first,
  44 pt targets, `100dvh`, safe-area insets); `static/vendor/htmx.min.js` plus
  `static/vendor/VERSIONS.txt`.
- `.env.example` (dummy values), `README.md` (what it is, local run, settings table).
- `tests/conftest.py` (temp migrated DB, `client` fixture whose default headers include the
  Origin, an autouse no-outbound-network guard), `tests/test_migrate.py`, `test_config.py`,
  `test_security.py`, `test_auth.py`.

**Behaviour to implement:** DESIGN sections 3, 8 and 12 for what exists so far. The app must
start in `oidc` mode **without reaching the issuer** (discovery is lazy, at first login) so
offline smoke runs work.

**Acceptance:**
- `uv sync --extra dev`
- `uv run ruff check && uv run ruff format --check`
- `uv run pytest -q` including tests that cover: migrations apply once and a second run applies
  nothing; `001_catalog.sql` creates the tables of DESIGN 4.1; deny-by-default for GET, HTMX and
  POST (302 with `next`, 401 + `HX-Redirect`, 401); `next` rejected unless it starts with a
  single `/`; group allow and deny (403, no session); rolling `seen` and the absolute cap;
  `AUTH_MODE=none` refused when `PUBLIC_URL` is not localhost; Origin check (403 without or
  with a foreign Origin); CSP and cache headers present; `SYNC_MIN_INTERVAL_S < 1` rejected.
- `uv run python -m polished migrate` prints the applied file once, and nothing the second time.
- With the local-run recipe: `curl -fsS localhost:8080/healthz` returns `status ok` and
  `schema 1`; `curl -fsS localhost:8080/ -o /dev/null -w '%{http_code}'` is 200.
- With `POLISHED_AUTH_MODE=oidc POLISHED_OIDC_CLIENT_ID=x POLISHED_OIDC_CLIENT_SECRET=x`:
  `curl -si localhost:8080/ | head -1` is a 302 whose `Location` is `/auth/login?next=%2F`;
  `curl -si -H 'HX-Request: true' localhost:8080/` is 401 with an `HX-Redirect` header;
  `curl -si -X POST -H 'Origin: http://localhost:8080' localhost:8080/anything` is 401 (without
  the Origin header it is 403: the Origin check runs before the gate, DESIGN 14 item 12); `/healthz` and `/static/css/app.css` are 200.
- `POLISHED_AUTH_MODE=none POLISHED_PUBLIC_URL=https://polished.janpuc.com uv run python -m
  polished serve` exits non-zero with a clear message.

**Out of scope:** any catalog logic, sync, shade pages, PWA files, Dockerfile, CI.

## Stage 2: catalog sync

**Goal:** the sync of DESIGN section 5, complete: classification, hashing, polite fetch, apply,
absence accounting, scheduler, `/sync` page and CLI.

**Create / change:**
- `src/polished/catalog/{classify,parse,hashing,fetch,sync,scheduler}.py`;
  `routes/sync.py`, `templates/{sync.html,_sync_status.html}`; the `sync` subcommand in `cli.py`
  (`sync` live, `sync --from-files …` offline); the lifespan hook that starts the scheduler
  (off when `POLISHED_SYNC_ENABLED=false`).
- `scripts/make_fixtures.py` (reads the local snapshot, writes the trimmed fixture) and the
  committed `tests/fixtures/feed_trimmed.json` plus `tests/fixtures/README.md`: about 14
  products, catalog fields only, covering the cases listed in DESIGN 5.4 (including one real
  shade whose `compare_at_price` the script raises, noted in the README).
- Tests: `test_classify.py`, `test_sync.py`, `test_fetch.py`, `test_scheduler.py`,
  `test_sync_routes.py`.

**Behaviour to test** (each is a named test): every fixture product lands in the expected role;
gifts are classified before bundles; a `bundles-sets`-only product is a bundle; the manual alias
resolves; hash ignores `updated_at` and `body_html` and changes on price, availability, tags and
image `src`; a second run over the same feed reports `changed_shades = 0`; price, availability
and retirement-tag changes propagate to `shade`; `is_topper`, `retired`, `retiring`;
`missing_since` after three absent runs, not on a feed below 70% of the last one, cleared when the
product returns; no shade row is ever deleted; an unresolved alias resolves on a later run;
fetch: three pages, at least 1 s between requests (injected clock), stops on a short page,
User-Agent set, a 429 or 5xx aborts the run with nothing written; scheduler `next_run_at`
(timezone, jitter bounds), catch-up condition, single flight, stale `running` row closed at
startup; manual run refused with 409 while running and 429 inside the cooldown.

**Acceptance:**
- `uv run pytest -q tests/test_classify.py tests/test_sync.py tests/test_fetch.py
  tests/test_scheduler.py tests/test_sync_routes.py`, then the full suite, `uv run ruff check`,
  `uv run ruff format --check`.
- Against the local snapshot (present in `research/`, untracked), offline:
  `uv run python -m polished sync --from-files research/p1.json research/p2.json research/p3.json`
  then
  `sqlite3 "$POLISHED_DB_PATH" "select role, count(*) from product group by role"` shows
  `alias 71`, `bundle 46`, `shade 372`, `skipped 37`;
  `select kind, count(*) from shade group by kind` shows `basecoat 4`, `polish 359`, `topcoat 9`;
  `select count(*) from shade_alias` is 71 (69 by handle plus the 2 manual aliases, all in the
  first run), `select count(*) from shade where retired = 1` is 118 and `retiring = 1` is 14;
  a second identical command leaves `select changed_shades from sync_run order by id desc limit 1`
  at 0.
- `curl -fsS localhost:8080/sync` is 200 and lists the run; `POST /sync/run` is **not** run
  against a real store (covered by tests with a mock transport).
- `grep -rn "updated_at" src/polished/catalog` shows it only in the hash exclusion list.

**Out of scope:** shade browse UI, per-product `.json` fetches, observations, events, alerts.

## Stage 3: browse, search and the PWA shell

**Goal:** The main user can find a shade on her phone: search, filters, detail page; the app installs
to the home screen.

**Create / change:**
- `shades.py` (search, filter, sort, pagination, `status()` per DESIGN 5.3, detail);
  `routes/{home,shades,pwa}.py`; `web.py` gets the `render()` partial rule of 3.2, money and
  thumbnail filters.
- Templates: `home.html` (search field with `hx-trigger="input changed delay:200ms"`),
  `shades.html`, `shade_detail.html`, `_shade_row.html`, `_filters.html`, `_search_results.html`,
  `offline.html`; routes `/`, `/search` (`ctx=home`), `/shades`, `/shades/{id}`.
- PWA: `/manifest.webmanifest`, `/sw.js` (rendered with the version, `Cache-Control: no-cache`),
  `/offline`, `scripts/make_icons.py` (run once with `uv run --with pillow`; the PNGs are
  committed: 180 apple-touch, 192, 512, maskable 512), `base.html` manifest, icon and
  `apple-mobile-web-app-*` tags, `htmx-config` meta (`historyCacheSize: 0`,
  `includeIndicatorStyles: false`).
- Tests: `test_shades.py` (token-AND search, accent folding, ranking order, each filter, sort
  keys, 40-row pages, the status table of 5.3 with a row per outcome), `test_routes_browse.py`
  (full page versus partial, `HX-History-Restore-Request` gets the full page, `Vary` and
  `Cache-Control`), `test_pwa.py` (manifest fields, service worker content and headers, offline
  page public).

**Acceptance:**
- Full suite and ruff green.
- With the local-run recipe after a fixture sync: `curl -s 'localhost:8080/shades?q=spirit'`
  contains a fixture shade title; the same URL with `-H 'HX-Request: true'` contains no `<html`;
  `curl -s 'localhost:8080/shades?finish=holographic&status=buyable' | grep -c 'class="shade-row'`
  matches the fixture's count (the test asserts the same number);
  `curl -s localhost:8080/shades/1` shows price and status label;
  `curl -s localhost:8080/manifest.webmanifest | python3 -m json.tool` succeeds;
  `curl -sI localhost:8080/sw.js | grep -i 'cache-control: no-cache'`;
  `curl -s 'localhost:8080/search?q=black&ctx=home'` returns rows without `<html`.
- Manual (Jan, once reachable): Add to Home Screen on iPhone, opens standalone, the offline
  page appears in airplane mode.

**Out of scope:** owned and wishlist badges and filters, scanner, wheels, `ctx=learn|stack`.

## Stage 4: bottles, wishlist, manual shades

**Goal:** answer "do I have this?" and "what do I still want?": bottles with state, the wishlist
with totals and the Shopify cart permalink.

**Create / change:**
- `migrations/002_inventory.sql` (DESIGN 4.2, verbatim); `bottles.py`, `wishlist.py`;
  `routes/{bottles,wishlist}.py`; manual-shade routes (`GET /shades/new` declared before
  `/shades/{id}`, `POST /shades`); `shades.py` gains owned/wishlist badges and the `owned`
  filter, using the `shade_status` view; `home.html` gains counts and recent bottles.
- `static/js/sheet.js`: the shared bottom-sheet `<dialog>` behaviour (open on swap into
  `#sheet-body`, close on the `sheetClose` event, backdrop click closes without discarding).
- Templates: `_bottles.html`, `_bottle_form.html` (sheet), `bottles.html`, `wishlist.html`,
  `_cart_box.html`, `shade_new.html`; the shade page and rows show owned count, state chips and
  the wishlist button.
- Tests: `test_bottles.py` (several bottles per shade; empty and archived bottles do not make a
  shade owned; state change; P code stored uppercase, normalised later), `test_wishlist.py`
  (one row per shade, priority bounds, total of all versus buyable, **the exact permalink
  string** `https://holotaco.com/cart/<variant_id>:1,…` with sold-out, retired-unavailable and
  missing shades excluded, `max_priority`), `test_routes_inventory.py` (partials, the
  `HX-Trigger: sheetClose` header, 404 and 403), a migration test that applies `002` on top of a
  synced `001` database.

**Acceptance:**
- Full suite and ruff green.
- With the recipe: `curl -s -X POST -H 'Origin: http://localhost:8080' -d state=half -d
  printed_code=259 localhost:8080/shades/1/bottles` returns a partial containing `P259`;
  `curl -s 'localhost:8080/shades?owned=owned'` lists that shade; the same POST without Origin is
  403; `curl -s -X POST -H 'Origin: http://localhost:8080' -d priority=1
  localhost:8080/shades/2/wishlist` then `curl -s localhost:8080/wishlist` shows the item and a
  total; `curl -s localhost:8080/wishlist/cart | grep -o 'holotaco.com/cart/[0-9:,]*'` prints the
  permalink for buyable items only.
- Manual (Jan): open a generated permalink in a browser and confirm the cart fills; the result
  is recorded in DESIGN 13.3.

**Out of scope:** learning P codes (the bottle only stores the code; stage 5 hooks learning
in), scanner, wheels, photos.

## Stage 5: identifier lookup and the scanner

**Goal:** scan a bottle's barcode or type a P code and land on the shade; unknown codes are
learned once.

**Create / change:**
- `migrations/003_identifiers.sql` (DESIGN 4.3); `gtin.py`, `identifiers.py` per DESIGN 7;
  `routes/lookup.py`; the learning hook in `bottles.create` (printed code → `printed` mapping,
  conflict keeps the old one and shows the notice); `/search?ctx=learn`; the Scan button on
  `home.html`; the add-bottle form pre-fills the P code and shade after a lookup.
- `static/js/scanner.js` per 7.3; vendored `static/vendor/zxing-wasm/` (reader build: the ES
  module and `zxing_reader.wasm`) with the version in `VERSIONS.txt`; `scripts/vendor.sh`
  documents how the pinned files were fetched (a developer step, not part of the build; the
  file layout of the pinned release is checked, not assumed).
- Templates: `lookup.html`, `_lookup_result.html` (one block per outcome), `identifiers.html`.
- Tests: `test_gtin.py` (`810065564276` and `0810065564276` both give `0810065564276`;
  `810170284120` gives `0810170284120`; `795203598` is rejected; a bad check digit is rejected;
  14 digits with and without a leading `0`; EAN-8 padded; surrounding whitespace),
  `test_identifiers.py` (each outcome of 7.2, order of the steps, a learned gtin is a `match`,
  a learned printed code is only a `suggestion`, a conflicting P code keeps the old mapping,
  delete, SKU lookup, nothing is ever seeded from catalog data), `test_routes_lookup.py`.

**Acceptance:**
- Full suite and ruff green.
- With the recipe: `curl -s 'localhost:8080/lookup/resolve?q=0810170284120&via=scan'` shows the
  "New barcode" block; `curl -s -X POST -H 'Origin: http://localhost:8080' -d kind=gtin -d
  value=810170284120 -d shade_id=1 localhost:8080/identifiers` saves it (normalised to 13
  digits); the same resolve call now shows a match for shade 1; after a bottle with
  `printed_code=259` exists, `…resolve?q=259` shows a suggestion, not a match;
  `…resolve?q=12345678901` shows `invalid_code`;
  `curl -sI localhost:8080/static/vendor/zxing-wasm/zxing_reader.wasm` is 200 with
  `content-type: application/wasm`; the response CSP contains `wasm-unsafe-eval`.
- Manual (Jan, iPhone, with the app reachable): scan the Spirit Fingers bottle (expect the
  barcode `810170284120`), pick the shade, scan again and get the match; try the photo fallback.
  If scanning does not work in practice, report it; do not work around it by seeding catalog
  barcodes.

**Out of scope:** fetching catalog barcodes, vision LLM, colour, wheels.

## Stage 6: wheels, slots, NFC and QR

**Goal:** wheels exist, each with a stable `/w/<slug>` page, a QR code and tag instructions;
slot tiles render (filling them is stage 7).

**Create / change:**
- `migrations/004_wheels_stacks.sql` (DESIGN 4.3: wheel, stack, stack_layer, wheel_slot, all
  four, so stage 7 adds no migration); add `segno` to dependencies; `wheels.py` (slug
  generation and retry, CRUD, slot grid read model, tag URL, QR, take-tag swap, highlight
  query); `routes/wheels.py` for everything in DESIGN 13.5 marked stage 6.
- Templates: `wheels.html`, `wheel.html` (4-column grid of `slot_count` tiles, `id="slot-N"`,
  `?hl=` highlight class, archived banner), `_slot_tile.html`, `wheel_tag.html`;
  `static/js/tag.js` (Copy button); the "Swatched on" section of `shade_detail.html` (query of
  DESIGN 4.3, empty until stage 7).
- Tests: `test_wheels.py` (slug alphabet and length 6, collision retry, regenerate, take swaps
  two slugs, archive keeps the slug, default `slot_count` 20, tile positions 1..20, the highlight
  query against hand-inserted stack rows), `test_qr.py` (SVG content type, body starts with
  `<svg`, differs per slug), `test_routes_wheels.py` (logged-out `/w/abc123` redirects to
  `/auth/login?next=%2Fw%2Fabc123` for known and unknown slugs alike; logged-in unknown slug is
  404; create redirects to the tag page).

**Acceptance:**
- Full suite and ruff green.
- With the recipe: `curl -si -X POST -H 'Origin: http://localhost:8080' -d name=Holos
  localhost:8080/wheels | grep -i '^location: /wheels/1/tag'`; the tag page contains
  `http://localhost:8080/w/` followed by 6 characters; `curl -s localhost:8080/w/<slug> | grep -c
  'id="slot-'` prints 20; `curl -sI localhost:8080/wheels/1/qr.svg` is 200 `image/svg+xml`;
  with `POLISHED_AUTH_MODE=oidc` (dummy client), `curl -si localhost:8080/w/abc123` is a 302 to
  `/auth/login?next=%2Fw%2Fabc123`.
- Manual (Jan): write an NFC tag with NFC Tools from the tag page URL; tapping it with the
  iPhone opens Safari on the wheel page (after login); the iOS camera opens the QR.

**Out of scope:** the stack builder and any layer editing, colour dots, photos.

## Stage 7: the layer-stack builder

**Goal:** fill a wheel slot with a free-form stack, x + y + z in order, on a phone.

**Create / change:**
- `stacks.py` (draft open/resume, append, move, coats, remove, templates, copy, save, cancel,
  clear, `summary()`, `default_coats()`), `routes/stacks.py` and the two slot routes in
  `routes/wheels.py`; `/search?ctx=stack` and the `owned|toppers|all` chips; `sheet.js`
  refocuses `#picker-q` after a layer swap.
- Templates: `_stack_sheet.html`, `_stack_layers.html`, `_picker_results.html`,
  `_copy_sources.html`; `_slot_tile.html` shows the summary, thumbnails and the draft dot; the
  shade page's "Swatched on" list links to `/w/<slug>?hl=<id>#slot-N`.
- Tests: `test_stacks.py` (append uses default coats: 1 for a top coat, 2 for polish; reorder
  swap via the temporary `ord`; remove renumbers; coats clamp 1..5; at most 8 layers; over black
  inserts at the base, is a no-op when already first, hidden when the handle is absent; copy
  duplicates rows not the stack; same-as-last; summary strings with Base/2nd/Top labels and `×N`
  only above 1; save replaces the old stack and clears the draft; cancel deletes the draft and
  an otherwise empty slot row; resume returns the same draft; clear removes stack, draft and row;
  operations on a non-draft stack are 409), `test_routes_stacks.py` (the full flow through the
  test client, `HX-Trigger: sheetClose` on save and cancel, out-of-band tile, "where used" on the
  shade page and `?hl=` on the wheel page).

**Acceptance:**
- Full suite and ruff green.
- With the recipe, after a fixture sync and `POST /wheels name=Holos`: open a draft
  (`curl -s -X POST -H 'Origin: http://localhost:8080' localhost:8080/wheels/1/slots/12/draft`),
  then `POST /stacks/1/layers` with `shade_id` three times, `POST /stacks/1/template/over-black`,
  `POST /stacks/1/layers/<id>/move -d dir=up`, `POST /stacks/1/save`; `curl -s
  localhost:8080/w/<slug> | grep -o 'id="slot-12"[^>]*'` shows a filled tile and its summary text
  contains ` + `; `curl -s localhost:8080/shades/<id>` shows "Swatched on" with the wheel name;
  `curl -s 'localhost:8080/w/<slug>?hl=<id>' | grep -c 'slot hl'` is at least 1.
- Manual (Jan, iPhone): build a three-layer stack in a real slot using the keyboard; report
  whether the keyboard stays open after a tap and whether the sheet fits; the result is written
  into DESIGN section 10 step 3.

**Out of scope:** mani, colour dots from `shade_colour`, drag and drop, sharing stacks between
slots.

## Stage 8: container, CI and release, home-ops files

**Goal:** the app builds as an image, CI and release-please are in place, and the home-ops
manifests exist as files for Jan to copy. Nothing is pushed or applied.

**Create:**
- `Dockerfile` modelled on serendip's: two stages on `python:3.12-slim`, uv from the pinned
  image, `uv sync --locked`, user `polished` uid 1000, `/data`, the build-time self-check
  (`import polished.server`, migrate a throwaway DB), `HEALTHCHECK` on `/healthz`,
  `CMD ["python", "-m", "polished", "serve"]`, `ARG POLISHED_VERSION`;
  `.dockerignore` (as serendip's, plus `research/`, `deploy/`).
- `.github/workflows/{ci.yml,release.yml,renovate.yaml}`, `release-please-config.json`,
  `.release-please-manifest.json` (`0.1.0`), `.renovaterc.json5`: serendip's files with the
  names changed (`polished`, `ghcr.io/janpuc/polished`, `src/polished/__init__.py` as the
  release-please extra file); action versions are taken from serendip's current files, not
  invented.
- `deploy/home-ops/selfhosted/polished/{ks.yaml,app/{kustomization,ocirepository,helmrelease,
  externalsecret,pocketidoidcclient}.yaml}` with the values of DESIGN 15, and
  `deploy/home-ops/README.md`: copy steps, the one `kustomization.yaml` line to add, the manual
  prerequisites, the first-deploy checklist. Every file is read against the mealie and
  serendip originals.
- `README.md` finished (status, screenshots not needed).

**Acceptance:**
- Full suite and ruff green.
- `docker build -t polished:test --build-arg POLISHED_VERSION=0.1.0 .` succeeds (the self-check
  runs inside it). If Docker is not available, say so; do not skip silently.
- `docker run --rm -u 1000 --read-only -v "$(mktemp -d):/data" -e POLISHED_DB_PATH=/data/polished.db
  polished:test python -m polished migrate` applies the four migrations; then a `docker run -d
  --read-only` with `POLISHED_AUTH_MODE=oidc`, a dummy client and `POLISHED_PUBLIC_URL=
  https://polished.example.test` answers `curl -fsS localhost:<port>/healthz` and redirects `/`
  to `/auth/login`; `docker inspect --format '{{.Config.User}}' polished:test` is `polished` or
  `1000`.
- `python3 -m json.tool release-please-config.json` and the manifest parse;
  `uv run --with pyyaml python -c "import glob,yaml; [list(yaml.safe_load_all(open(f))) for f in
  glob.glob('deploy/home-ops/**/*.yaml', recursive=True)+glob.glob('.github/workflows/*')]"`
  succeeds; `grep -rniE 'password|secret' deploy/home-ops` shows only references to secret
  names and keys, no values.
- `git status --short` shows no staged files, and `git status --short --ignored` lists
  `research/p*.json`, any `.db` and `.env` only under `!!` (ignored), never as untracked or staged.

**Manual after the stage, by Jan (not an agent):** create the repo and push; add
`OP_SERVICE_ACCOUNT_TOKEN`; create the 1Password item `polished`; make the package public;
copy `deploy/home-ops/` into home-ops on a branch; first deploy checklist: log in through Pocket ID
in Safari and in the installed PWA, check `/sync` shows the catch-up run and 372 shades, scan a
bottle, tap a tag, build a stack.

**Out of scope:** editing home-ops, pushing, creating the repo, v2 features.

## v2 (after v1 has been used for a few weeks)

In rough order of value, each its own stage:

1. **Colour extraction and dupe check:** `shade_colour`, Pillow + numpy, the method in the advice
   (macro image first, centre crop, near-white/black and skin filters, 3-cluster k-means in Lab,
   ΔE2000 plus finish-tag penalty), a manual image override, "you own N close shades" on the
   shade page and wishlist; colour dots in stack chips.
2. **Observations and alerts:** `shade_observation` appended by sync on change, `event` queue,
   an in-app "what's new" feed, a daily Matrix digest through one notifier function behind
   `POLISHED_MATRIX_WEBHOOK_URL` (wishlist back in stock, on sale, retiring; new shades).
3. **Collection progress:** "5/8 of Brainrot" from `shade_tag` collections.
4. **Read-only share link:** `/share/<token>`, names, images, prices and the cart permalink
   only, `noindex`, `no-store`, revocable.
5. **Vision-LLM fallback** for bottle photos (LiteLLM, `*-local` alias, fails soft), only if
   barcodes disappoint in practice.
6. Possibly: seed catalog barcodes if a real bottle ever matches one (DESIGN section 7).

## v3

1. **Mani log:** `mani` with its own stack (same builder, holder = mani), photos under
   `/data/photos` resized on upload (and the kopiur capacity raised), "not worn in a while".
2. **Tap-to-sample colours** on wheel and mani photos (median over a small radius, stored as
   `shade_colour` with source `wheel`).
3. **Random picker** ("what shall I wear"), filterable by owned finish and colour.
