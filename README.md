# polished

A self-hosted nail polish inventory for one household, fed by the
[Holo Taco](https://holotaco.com) catalog. Server-rendered FastAPI + Jinja2 + HTMX on one SQLite
file, with Pocket ID sign-in.

Status: the v1 feature set is built and not yet deployed. It covers the daily Holo Taco catalog
sync, browse and search, bottles with their level and purchase history, the wishlist with a Holo
Taco checkout link and "I bought these", barcode and P-code lookup, swatch wheels with NFC/QR tags,
the layer builder, and painted-nail tips drawn from each shade's sampled colour and finish. It
installs to a phone's home screen. The brief is in [`docs/BRIEF.md`](docs/BRIEF.md), the design in
[`docs/DESIGN.md`](docs/DESIGN.md), the look in [`docs/VISUAL.md`](docs/VISUAL.md) and the build
plan in [`docs/PLAN.md`](docs/PLAN.md).

## Container and deploy

`docker build -t polished --build-arg POLISHED_VERSION=0.1.0 .` builds the image (python:3.12-slim,
uid 1000, data in `/data`, port 8080, healthcheck on `/healthz`). The build fails if the package,
its migrations or its static files are missing. Release-please versions the app from Conventional
Commits and the `Release` workflow publishes `ghcr.io/janpuc/polished`. The home-ops manifests are
in [`deploy/home-ops/`](deploy/home-ops/) and the steps to take them live are in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

## Running locally

```sh
uv sync --extra dev
export POLISHED_DB_PATH=./data/polished.db POLISHED_AUTH_MODE=none \
       POLISHED_PUBLIC_URL=http://localhost:8080
uv run python -m polished migrate
uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json --no-colours   # offline
uv run python -m polished serve    # http://localhost:8080
uv run pytest -q
uv run ruff check && uv run ruff format --check
```

`POLISHED_AUTH_MODE=none` switches sign-in off and is refused unless `POLISHED_PUBLIC_URL` is
`localhost` or `127.0.0.1`. `.env.example` lists the development settings with dummy values; copy
it to `.env` (untracked) if you prefer a file.

Smoke test against a throwaway database:

```sh
export POLISHED_DB_PATH=$(mktemp -d)/polished.db POLISHED_AUTH_MODE=none \
       POLISHED_PUBLIC_URL=http://localhost:8080 POLISHED_SYNC_ENABLED=false \
       POLISHED_SESSION_SECRET=dev-secret-dev-secret-dev-secret-00
uv run python -m polished migrate
uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json --no-colours
(uv run python -m polished serve & echo $! > /tmp/polished.pid); sleep 2
curl -fsS localhost:8080/healthz      # {"status":"ok","version":"dev","schema":1}
curl -fsS localhost:8080/sync         # the run just made
kill $(cat /tmp/polished.pid)
```

## Testing

```sh
uv run ruff check && uv run ruff format --check
uv run pytest -q          # unit and route tests; no network, no browser
```

**Browser flows** (not part of `pytest -q`) walk through the app like a person: search with typos,
add a bottle and change its level, the wishlist and "I bought these", build a swatch on a wheel,
delete a wheel, scan a bottle from a photo, browse with filters, the history page, and a tour of
every tab. Each flow is a list of named steps that assert something and save a screenshot, and
runs on an iPhone, an iPad and a Mac (Chromium with Playwright's device profiles) in light and dark.
After every step it also checks for console errors, failed requests, 4xx/5xx answers, horizontal
overflow and, on the touch devices, tap targets under 44 points.

```sh
uvx --from playwright playwright install chromium     # once; kept in ~/Library/Caches/ms-playwright
uvx --from playwright --with python-barcode --with pillow python tests/e2e/run_flows.py
uvx --from playwright --with python-barcode --with pillow python tests/e2e/run_flows.py \
    --devices iphone --schemes dark --flows search,wheel-delete     # a part of it
```

The runner starts the app itself for every flow on a fresh copy of a database seeded from
`tests/fixtures/` (sign-in off, no network, nothing from holotaco.com), so flows never see each
other's data; the full run is 60 runs and takes about five minutes. It prints one line per run and
writes `~/.cache/polished/flows/<timestamp>/` (outside the repo; `--out DIR` changes it) with
`index.html` (one row per flow, device and scheme: the step screenshots, PASS or FAIL, and the failure
text under the step that failed) and `summary.json`. The exit status is 1 if any step failed.
`--list` shows the flows, `--tap-warnings` turns the tap-target audit into notes, and `--base URL`
runs against a server you started yourself, which must be a throwaway on a database made with
`uv run python tests/e2e/flows/seed.py DB` and whose `POLISHED_PUBLIC_URL` is that address.

The flows live in `tests/e2e/flows/` (`scenarios.py` has them, `harness.py` the steps and audits).
`tests/e2e/builder_smoke.py` and `scanner_smoke.py` are the older single-purpose smoke tests and
still run on their own.

## Scanning

`/lookup` reads a bottle's barcode with the phone camera (zxing-wasm, in the page, no cloud) or
from a photo, and resolves a typed barcode, P code or name. A barcode is learned once (scan, pick
the shade) and then matches; a P code is only ever a suggestion. Catalog barcodes are not used.
The camera needs https (or `localhost`); on a plain-http address the page says so and "Take a photo instead"
and the typed field still work.

A headless-browser smoke test (not part of `pytest -q`) decodes a generated barcode through the
photo input and a fake camera. With the server running on a fresh throwaway database (the
recipe above):

```sh
uvx --from playwright --with python-barcode --with pillow python tests/e2e/scanner_smoke.py
```

It needs Playwright's Chromium (`uvx --from playwright playwright install chromium`).

## Catalog sync

The app syncs the shop's public `products.json` feed once a day (06:00 local plus up to 30
minutes of jitter), once at startup if the last good run is older than 30 hours, and on demand
from `/sync`. That is 3 requests a day, at least a second apart, with an identifying User-Agent.
`python -m polished sync` does one live run; `sync --from-files PAGE.json ...` applies local
pages with the same code and no request to the shop (use this for development: `tests/fixtures/`
holds a trimmed feed, and a full snapshot of three pages works too). The run's last step reads each
shade's polish colour from its product photo and downloads those photos from the Shopify image CDN
(cdn.shopify.com), so `--from-files` alone is not offline; add `--no-colours` to skip that step and
touch no network at all (`python -m polished colours` does the step later). A 429 or 5xx stops the
run with nothing written. Shades are never deleted.

After the shop pages the sync reads Holo Taco's official release list (a public Google Sheet, CSV
export, one request) for each shade's release date, official collection name and retired flag, and
adds the few shades the sheet lists and the shop does not as "Not in the shop" shades you can still
own, swatch and wish for. A sheet that fails or changes layout is logged as a warning and changes
nothing; the shop sync never depends on it. `POLISHED_RELEASE_SHEET_URL` changes the address (empty
turns it off); `sync --from-files PAGE.json ... --sheet SHEET.csv` applies a local copy.

## Settings

Environment variables, all prefixed `POLISHED_` (see `src/polished/config.py`). Secrets come only
from the environment.

| Variable | Default | Meaning |
|---|---|---|
| `POLISHED_PUBLIC_URL` | required | External base URL (`https://polished.janpuc.com`): OIDC redirect, QR and tag URLs, the host the Origin check expects |
| `POLISHED_DB_PATH` | `/data/polished.db` | SQLite file |
| `POLISHED_AUTH_MODE` | `oidc` | `oidc` or `none` (development only, localhost `PUBLIC_URL` only) |
| `POLISHED_OIDC_ISSUER` | `https://id.janpuc.com` | Discovery at `<issuer>/.well-known/openid-configuration`, read at the first login |
| `POLISHED_OIDC_CLIENT_ID`, `POLISHED_OIDC_CLIENT_SECRET` | unset | Required in `oidc` mode |
| `POLISHED_OIDC_ALLOWED_GROUPS` | `ID-Users,ID-Admin` | Comma-separated, exact match against the token's `groups` claim |
| `POLISHED_SESSION_SECRET` | unset | At least 32 characters; required in `oidc` mode (a random one is made per start in `none` mode) |
| `POLISHED_SESSION_DAYS`, `POLISHED_SESSION_MAX_DAYS` | `30`, `90` | Cookie lifetime, and the absolute session age after which sign-in is repeated |
| `POLISHED_HOST`, `POLISHED_PORT` | `0.0.0.0`, `8080` | Listener |
| `POLISHED_STORE_URL` | `https://holotaco.com` | Shop base for the feed and cart permalinks |
| `POLISHED_SYNC_ENABLED` | `true` | Daily catalog sync on or off (the button and the CLI still work) |
| `POLISHED_SYNC_HOUR`, `POLISHED_SYNC_JITTER_MIN` | `6`, `30` | Daily run, local time, plus up to this many minutes of jitter |
| `POLISHED_SYNC_MIN_INTERVAL_S` | `1.0` | Gap between requests to the store; values below `1.0` are refused |
| `POLISHED_SYNC_MANUAL_COOLDOWN_S` | `3600` | Minimum time between runs started from the page |
| `POLISHED_RELEASE_SHEET_URL` | the CSV export of Holo Taco's release list | Read once per sync after the shop pages, for release dates, collections and retired flags; empty turns it off |
| `POLISHED_TIMEZONE` | `Europe/Warsaw` | Household timezone |
| `POLISHED_OVER_BLACK_HANDLE` | `one-coat-black` | Shade the "Over black" template inserts (stage 7) |
| `POLISHED_LOG_LEVEL`, `POLISHED_VERSION` | `INFO`, `dev` | Logging; the image build sets the version |

## Third-party files

`src/polished/static/vendor/` holds vendored browser libraries; versions and checksums are in
`VERSIONS.txt` there. There is no build step and no Node.
`scripts/vendor.sh` re-fetches the pinned files (htmx, zxing-wasm) and checks their sha256.
There is no webfont: the UI is set in the system font (SF Pro on an iPhone).

## Look and icons

`docs/VISUAL.md` is the spec for how the app looks ("the swatch book": a quiet board in ink and plum,
every shade a painted nail tip, pink only for the heart); all of it lives in `static/css/app.css` as
tokens and components, with light and dark from the system setting. The logo is two hand-drawn
SVGs in `static/icons/` (`logo.svg`, `favicon.svg`); after editing one, redraw the PNGs
(apple-touch, PWA, maskable, favicon fallback) with Chromium:

```sh
uvx --from playwright python scripts/make_icons.py
```
