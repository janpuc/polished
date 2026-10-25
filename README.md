# polished

A self-hosted nail polish inventory for one household, fed by the
[Holo Taco](https://holotaco.com) catalog. Server-rendered FastAPI + Jinja2 + HTMX on one SQLite
file, with Pocket ID sign-in.

Status: stage 5 of the v1 build (skeleton, storage, authentication, the catalog sync, browse,
search and the PWA shell, bottles and the wishlist, and identifier lookup with the barcode
scanner). It serves `/healthz`, the sign-in flow, a search home page, `/shades` with filters and a
detail page per shade, bottles and the wishlist with a Holo Taco checkout link, `/lookup` (scan a
barcode or type a P code), the `/sync` page and the daily catalog sync, and installs to a phone's
home screen; wheels and the layer builder come in later stages. The brief is in
[`docs/BRIEF.md`](docs/BRIEF.md), the design in [`docs/DESIGN.md`](docs/DESIGN.md) and the build
plan in [`docs/PLAN.md`](docs/PLAN.md).

## Running locally

```sh
uv sync --extra dev
export POLISHED_DB_PATH=./data/polished.db POLISHED_AUTH_MODE=none \
       POLISHED_PUBLIC_URL=http://localhost:8080
uv run python -m polished migrate
uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json   # offline
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
uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json
(uv run python -m polished serve & echo $! > /tmp/polished.pid); sleep 2
curl -fsS localhost:8080/healthz      # {"status":"ok","version":"dev","schema":1}
curl -fsS localhost:8080/sync         # the run just made
kill $(cat /tmp/polished.pid)
```

## Scanning

`/lookup` reads a bottle's barcode with the phone camera (zxing-wasm, in the page, no cloud) or
from a photo, and resolves a typed barcode, P code or name. A barcode is learned once (scan, pick
the shade) and then matches; a P code is only ever a suggestion. Catalog barcodes are not used.
The camera needs https (or `localhost`); on a plain-http address the page says so and the photo
button and the typed field still work.

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
pages with the same code and no network (use this for development: `tests/fixtures/` holds a
trimmed feed, and a full snapshot of three pages works too). A 429 or 5xx stops the run with
nothing written. Shades are never deleted.

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
| `POLISHED_TIMEZONE` | `Europe/Warsaw` | Household timezone |
| `POLISHED_OVER_BLACK_HANDLE` | `one-coat-black` | Shade the "Over black" template inserts (stage 7) |
| `POLISHED_LOG_LEVEL`, `POLISHED_VERSION` | `INFO`, `dev` | Logging; the image build sets the version |

## Third-party files

`src/polished/static/vendor/` holds vendored browser libraries; versions and checksums are in
`VERSIONS.txt` there. There is no build step and no Node.
`scripts/vendor.sh` re-fetches the pinned files (htmx, zxing-wasm) and checks their sha256.
There is no webfont: the UI is set in the system font (SF Pro on an iPhone).

## Look and icons

`docs/VISUAL.md` is the spec for how the app looks; all of it lives in `static/css/app.css` as
tokens and components, with light and dark from the system setting. The logo is two hand-drawn
SVGs in `static/icons/` (`logo.svg`, `favicon.svg`); after editing one, redraw the PNGs
(apple-touch, PWA, maskable, favicon fallback) with Chromium:

```sh
uvx --from playwright python scripts/make_icons.py
```
