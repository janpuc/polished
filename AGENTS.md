# polished

A self-hosted nail polish inventory for one household, fed by the holotaco.com catalog. Start
with `docs/BRIEF.md` (goal, verified facts, Jan's answers), then `docs/DESIGN.md` (architecture,
schema, routes, algorithms) and `docs/PLAN.md` (the staged v1 build). `docs/advice/` holds the
advisor's recommendation the design started from; DESIGN.md wins where they differ.

- Follow `~/.pi/agent/AGENTS.md`: delegate bounded jobs to subagents (one or two at a time),
  check `usage_status` and pick the lowest model level that fits, ask the `oracle` advisor
  (`openai/gpt-6-astra:high`) before changing the design, not while building.
- Work in the stages of `docs/PLAN.md`, one stage per agent run. Each stage leaves a runnable
  app and ends with its acceptance commands passing. After each stage, report to Jan what
  changed and which commands you ran. A subagent running a stage stops at the end of its stage.
- Never touch the live cluster or push home-ops. Home-ops manifests live under `deploy/home-ops/`
  in this repo for Jan to copy; they are never applied from here.
- The repo is public at github.com/janpuc/polished (Jan's yes, 2026-10-25). Subagents never
  commit or push; the orchestrating session commits a stage after checking it and pushes.
- Holo Taco is a small shop: sync is 3 `products.json` requests a day, at most 1 request per
  second, with an identifying User-Agent. Tests and local runs use `tests/fixtures/` or a local
  snapshot (`polished sync --from-files ... --no-colours`; without the flag the colour step downloads
  photos from cdn.shopify.com), never the live store. A 429 or 5xx means stop and
  report, not retry in a loop. Never use `updated_at` as a change signal and never delete a shade.
- This repo is public: no secrets, no `.env` files, no personal data, no real database, no
  `research/*.json` snapshot, no photos. Config comes from `POLISHED_*` environment variables;
  `.env.example` documents them with dummy values. Test fixtures hold catalog fields only.
- Mutating routes are POST (HTMX or plain forms); there is no client-side state and no build
  step. JS is plain ES modules in `src/polished/static/js/`, third-party files are vendored
  under `static/vendor/` with their version recorded, and the CSP forbids inline scripts.
- Python 3.12, uv, FastAPI, Jinja2 + HTMX, SQLite (stdlib `sqlite3`, numbered SQL migrations in
  `src/polished/migrations/`, never edit an applied migration), authlib, httpx, ruff, pytest.
  Keep `docs/DESIGN.md` current: if the code and the doc disagree, fix one in the same change.

## Commands

```sh
uv sync --extra dev
uv run ruff check && uv run ruff format --check
uv run pytest -q
export POLISHED_DB_PATH=./data/polished.db POLISHED_AUTH_MODE=none POLISHED_PUBLIC_URL=http://localhost:8080
uv run python -m polished migrate
uv run python -m polished sync --from-files research/p1.json research/p2.json research/p3.json --no-colours
uv run python -m polished serve          # http://localhost:8080
uvx --from playwright --with python-barcode --with pillow python tests/e2e/run_flows.py   # browser flows
```

`tests/e2e/run_flows.py` is the observable end-to-end suite (not part of `pytest -q`; needs
Chromium, see the README's Testing section): named flows with screenshots on an iPhone, an iPad and
a Mac in light and dark, on a fresh seeded database per flow, a report in
`~/.cache/polished/flows/<timestamp>/index.html` and exit 1 on any failure. Run it after changing
templates, routes or htmx behaviour, and add a flow to `tests/e2e/flows/scenarios.py` for a new
screen. Selectors are roles, labels and text, so a restyle should not break it; `--flows` and
`--devices` narrow a run. Never point it at the live app (`--base` takes a throwaway server only).

Commit messages are Conventional Commits (release-please reads them): `feat:`, `fix:`,
`docs:`, `build:`, `ci:`, `test:`, `chore:`. Dependency PRs from Renovate use `chore(deps):`.
