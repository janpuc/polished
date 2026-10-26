# polished native: the SwiftUI app for iPhone, iPad and iPhone Duo (phase 2, TestFlight v1)

2026-10-26. Author: Fable (oracle, design director). Builds on `docs/ROADMAP.md` phase 2, `docs/advice/fable-v3-web-2026-10-26.md` (the v3 language), `docs/DESIGN.md` (the rules the server already enforces). No repo file was changed by this session; committed as `docs/NATIVE.md`.

Verified on this Mac today: Xcode 27.1 (27A9275) with the iOS 27.1 SDK, Swift 6.4, `altool` 1.1.3, `xcresulttool export attachments`, `simctl ui appearance|increase_contrast`; the `iPhone Duo`, `iPhone 18 Pro` and `iPad Pro 13-inch (M5)` simulator device types exist and (checked again after Jan ran `-downloadPlatform`) the iOS 27.0 and 27.1 simulator runtimes are installed; `xcodegen` is not installed (brew has 2.46.0). API availability was checked against developer.apple.com's documentation JSON (section 10 lists every source).

---

## 1. Product scope of TestFlight v1

Everything the web app does today, done natively, plus the four things only an app can do. One shared household collection, two signed-in people.

**Keep (parity with the web, all of it):** Home shelf (greeting, Wear today with "I wore this" and "Another", the rack, the wheel card, the collection numbers); Shades (ranked fuzzy search with the matched spans highlighted, the full filter set, Load more); Shade detail (lit hero tip, photo strip, price and status, Add bottle, heart, bottles, facts, Swatched on, Tip colour override, store link); Bottles (groups, level, edit, archive, delete) and History; Wishlist (priorities, notes, totals, Holo Taco checkout link, Copy list, I bought these); Wheels (list, create, rename, archive, delete with confirmation, New tag URL, Take the tag of…); the wheel ring and the full builder (append, coats, move, remove, Over black, Copy from…, Same as last, name, note, painted-on date, save, cancel, remove swatch, resumed drafts); Lookup (typed codes and names, learn a code, learned codes, "This isn't it"); manual shade; Sync status and Sync now; sign out.

**Add (native only):**
1. **Core NFC writing** of the wheel's `https://polished.janpuc.com/w/<slug>` to a sticker, in the app, with a read-back check.
2. **The sticker opens the app on the wheel** through a universal link (AASA + Associated Domains); Safari only when the app is not installed. Same for QR codes read by the Camera app and for `/shades/<id>` links.
3. **VisionKit live barcode scanning** (EAN-13, UPC, EAN-8) with the resolver of DESIGN 7; the photo fallback goes away (live scanning is sharper than the web's video frames).
4. **Light that moves:** the lit tip of v3 plus a tilt-reactive specular and holo shift (Metal shader driven by Core Motion), gated by Reduce Motion and Low Power Mode.
5. **Haptics**, native date pickers, sheets with detents, zoom transitions, Dynamic Type, VoiceOver done properly.
6. **One widget:** "Wear today" (small and medium), fed by a snapshot the app writes to the App Group; tapping opens the shade.

**Cut from v1 (deliberately):** App Intents, Spotlight indexing and Shortcuts (nothing she would use before the wheel tag; v1.1 if cheap then); a wheel widget; offline writes (DESIGN's "never" stands: reads work offline from the cache, every write needs the server); photo capture or colour sampling on the device (the server samples, as before); editing manual shades; a Passport page; Mac. **Do not enable "Designed for iPad" on Mac:** the Mac keeps the web app by decision, and an installed iPad app on the Mac would capture the `/w/*` and `/shades/*` universal links in Safari there and hijack Jan's web use. It is one checkbox in App Store Connect ("Make available on Mac") and stays off; revisit only if Jan wants a native Mac shelf.

**Two users, one collection, kept.** The server has one shared collection for every signed-in person and that stays in phase 2 (it is a household inventory; "who added it" is not a question anyone asks). Users matter for sign-in and for per-device tokens (revocation, "last used"). Multi-user tenancy is phase 3.

**Minimum OS:** build with the iOS 27.1 SDK, deployment target **iOS 26.0**, with `if #available(iOS 27.1, *)` around the three Duo-only APIs (`ReservedRegion`, `ArrangementView`, `toolbarVerticalBehavior`). Reason: Nikola's iPhone and its OS version are unverified; everything the design needs (Liquid Glass, zoom transitions, detents, Swift Testing, SwiftData) is iOS 26 or older. If Jan confirms both phones run iOS 27, raise the target to 27.1 and delete the gates in run 6.

---

## 2. Architecture

### 2.1 Repository layout (monorepo, `app/` and `spec/`)

```
app/
  project.yml                       XcodeGen spec (the .xcodeproj is generated, gitignored)
  Polished/                         iOS app target (iPhone + iPad)
    App/                            PolishedApp.swift, AppModel, Router, DeepLinks
    Design/                         Tokens, Fonts, TipView, LevelArc, Rack, Ring, Ledge, Glass rules
    Features/{Home,Shades,ShadeDetail,Bottles,Wishlist,Wheels,Builder,Scan,Tag,Settings,SignIn}/
    Resources/                      Assets.xcassets (colours, AppIcon), Fonts/Fraunces144pt-SemiBold.ttf
    Polished.entitlements, Polished-Debug.entitlements, Info.plist
  PolishedWidgets/                  WidgetKit extension ("Wear today")
  PolishedCore/                     Swift package, no UIKit above the renderer
    Sources/PolishedModels/         Codable DTOs, enums, labels, GTIN + printed-code normalisation
    Sources/PolishedAPI/            PolishedAPI protocol, LiveAPI (URLSession), FixtureAPI (previews, widget tests)
    Sources/PolishedStore/          SwiftData cache + Session (Keychain) + write coordinator
    Sources/NailTips/               TipRandom, TipPainter (ops), TipCanvas (drawing), TipShape, TipLight (shader glue)
    Sources/NailTips/Shaders/       TipLight.metal
    Tests/PolishedCoreTests/        Swift Testing: fixtures parity, decoding, normalisation
  PolishedUITests/                  XCUITest flows + Screenshots helper
  Scripts/                          flows.sh, report.py, archive-upload.sh, bump-build.sh
spec/
  tips/cases.json, tips/random.json   renderer conformance (both engines)
  identifiers/gtin.json, printed.json normalisation vectors
  api/openapi.yaml                    the /api/v1 contract
  api/fixtures/*.json                 recorded responses from the seeded e2e database
```

The package name `NailTips` avoids Apple's `TipKit`. `spec/` is CC0 and holds no personal data (catalog fields and invented bottles only, like `tests/fixtures/`).

### 2.2 Targets, identifiers, entitlements (project.yml)

| Target | Bundle ID | Notes |
|---|---|---|
| `Polished` | `com.janpuc.polished` | iOS app, `TARGETED_DEVICE_FAMILY 1,2`, `SUPPORTS_MACCATALYST NO`, `SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD NO`, all orientations on iPad, portrait + landscape on iPhone (Duo rotates), `UIRequiresFullScreen NO` |
| `PolishedWidgets` | `com.janpuc.polished.widgets` | WidgetKit extension |
| `PolishedTests` | `com.janpuc.polished.tests` | hosts PolishedCore tests too (`xcodebuild test` runs the package tests through the scheme) |
| `PolishedUITests` | `com.janpuc.polished.uitests` | XCUITest |

Settings: `SWIFT_VERSION 6.0` with strict concurrency, `IPHONEOS_DEPLOYMENT_TARGET 26.0`, `MARKETING_VERSION 1.0.0`, `CURRENT_PROJECT_VERSION` set by `Scripts/bump-build.sh` (`YYYYMMDDHHMM`, UTC), `DEVELOPMENT_TEAM` from `app/Team.xcconfig` (gitignored; template `Team.xcconfig.example`; the team ID is not secret, it appears in the public AASA, but it stays out of the public project file anyway), `CODE_SIGN_STYLE Automatic`, `ITSAppUsesNonExemptEncryption NO` (HTTPS only; skips the export-compliance question on every upload).

`Polished.entitlements`:
```xml
com.apple.developer.nfc.readersession.formats  = [ NDEF ]
com.apple.developer.associated-domains         = [ applinks:polished.janpuc.com ]
com.apple.security.application-groups          = [ group.com.janpuc.polished ]
```
`Polished-Debug.entitlements` adds `applinks:polished.janpuc.com?mode=developer` so a development build reads the AASA straight from the server (needs Developer Mode → "Associated Domains Development" on the device). Widget: the App Group only. No Keychain sharing: the widget never holds the token.

`Info.plist`: `NFCReaderUsageDescription` "Polished writes the wheel's link to a sticker and checks it.", `NSCameraUsageDescription` "Polished reads the barcode under a bottle.", `CFBundleURLTypes` scheme `polished` (sign-in callback), `UIAppFonts` [Fraunces144pt-SemiBold.ttf], `UIApplicationSceneManifest` with `UIApplicationSupportsMultipleScenes YES` (Split View and Stage Manager). No `NSMotionUsageDescription`: `CMMotionManager` attitude does not need one.

### 2.3 Modules and data flow

- **`PolishedAPI`**: `protocol PolishedAPI: Sendable` with one async method per contract endpoint, typed DTOs in, DTOs out, `APIError` (`.unauthorized`, `.notFound`, `.conflict(code)`, `.validation(fields)`, `.offline`, `.server(status)`). `LiveAPI` uses one `URLSession` (ephemeral config, `waitsForConnectivity false`, 15 s timeout), `Authorization: Bearer`, `User-Agent: polished-ios/<version>`, ETag store per URL (`If-None-Match`, 304 → cached body). `FixtureAPI` answers from `spec/api/fixtures/` for previews and the widget tests only; UI tests use the real server (section 6).
- **`PolishedStore`**: an actor-isolated SwiftData container (`Snapshot` entity: `key`, `etag`, `json`, `fetchedAt`) keyed by resource (`home`, `shades?<query>`, `shade/<id>`, `bottles`, `history`, `wishlist`, `wheels`, `wheel/<slug>`, `me`). Every screen renders the snapshot first (instant launch, offline reading) and revalidates on appear and on `scenePhase == .active`. Writes go through `WriteCoordinator`: the UI applies the expected result immediately for the four toggles (wishlist heart, priority, bottle level, "I wore this"), sends the request, replaces the optimistic state with the response, and on failure reverts with a status line ("Couldn't save. Still half." ) and one automatic retry after 2 s on timeouts only. Everything else (add bottle, bought, stack edits, save swatch, delete wheel) awaits the server and shows a progress state ≥ 300 ms only. No queue, no offline writes.
- **`AppModel`** (`@Observable @MainActor`): `session` (signed out / signed in with user), `api`, `store`, `router` (tab, per-tab `NavigationPath`, pending deep link), `tipLight` (section 4.4), `serverURL` (`https://polished.janpuc.com` by default; a hidden long-press on the Settings version row allows another server in DEBUG builds and a `-server` launch argument for UI tests).
- **Deep links**: `.onOpenURL` (universal links arrive here under the SwiftUI lifecycle) → `Router.open(URL)`: `/w/<slug>` → Wheels tab, push `WheelScreen(slug)`; `/shades/<id>` → Shades tab, push detail; anything else → Home. Validate the slug against `^[0-9a-hj-km-np-tv-z]{6}$` and the id as an integer; ignore the rest. Signed out: keep the URL as `pendingLink`, run sign-in, then open it.

### 2.4 Sign-in

`ASWebAuthenticationSession` through the server's existing Pocket ID flow, ending in a per-device token in the Keychain.

```
app:    verifier = 32 random bytes (base64url); challenge = base64url(SHA256(verifier))
        ASWebAuthenticationSession(url: <server>/auth/app/start?challenge=<c>&device=<"Nikola's iPhone">,
                                   callback: .customScheme("polished"))   prefersEphemeralWebBrowserSession = false
server: GET /auth/app/start  → session["app_login"] = {challenge, device, iat}; 302 /auth/login?next=/auth/app/finish
        (Pocket ID as today: passkey, remember-me, group check)
        GET /auth/app/finish → signed in; mints code (32 random bytes, 60 s TTL, single use, bound to sub + challenge)
                                302 polished://auth?code=<code>
app:    POST /api/v1/auth/exchange {code, verifier, device_name, platform:"ios", app_version}
server: checks TTL, single use, SHA256(verifier) == challenge → inserts api_token, answers {token, token_id, user}
app:    Keychain generic password, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly, service "com.janpuc.polished", account "api-token"
```

`prefersEphemeralWebBrowserSession` is false so Pocket ID's passkey and remember-me are shared with Safari (she signs in once). The `https(host:path:)` callback form exists (iOS 17.4) but needs a `webcredentials:` association; the custom scheme is enough here. Tokens never expire by time; they are revoked by **Sign out** (`POST /api/v1/auth/revoke`), from the web's More page ("Devices", a phase-1 addition listed in the contract), or by deleting the row. A 401 from any call clears the Keychain and shows the sign-in screen with the reason. Token storage on the server is `sha256(token)`; the token is shown to nobody after the exchange.

---

## 3. The server contract: `/api/v1`

Built by a separate worker (runs S1 and S2 in section 8). Written as the contract a future standalone engine or another server meets too: JSON only, integers for ids (opaque to clients, no arithmetic), cents for money, ISO dates (`YYYY-MM-DD`) and UTC timestamps (`…Z`), the tip recipe inline (no SVG URLs needed by the app), nothing HTMX- or template-shaped. Source of truth: `spec/api/openapi.yaml`; recorded examples: `spec/api/fixtures/*.json`, exported from the seeded e2e database by `scripts/make_api_fixtures.py`.

**Transport rules.** `Authorization: Bearer <token>` is the only credential the API accepts (cookies are ignored under `/api/v1/`), so the Origin check and CSRF do not apply there; `OriginCheckMiddleware` skips `/api/v1/` when a Bearer header is present. 401 for a missing, unknown or revoked token with `{"error":{"code":"unauthorized"}}`. Every GET answers `ETag` and honours `If-None-Match` (304, empty body); `Cache-Control: private, no-cache`. `X-Polished-Api: 1` on every answer. Versioning: additive changes within v1 (new optional fields, new endpoints); a breaking change is `/api/v2`. Rate etiquette unchanged: the API never contacts the shop except `POST /sync/run` with the existing cooldown.

**Errors.** `{"error": {"code": "<snake_case>", "message": "<her words>", "field": "<optional>"}}` with the status: 400 `bad_request`, 401 `unauthorized`, 403 `forbidden`, 404 `not_found`, 409 `not_a_draft` | `sync_running`, 422 `validation` (`field` set, `message` as the web shows it: "Use an amount like 15.50."), `stack_full`, `empty_stack`, `same_wheel`, 429 `cooldown` (`retry_after_s`), 5xx `server_error`.

**Shared shapes.**
```jsonc
Tip      {"id": 12, "hex": "#c72bb9", "hex2": null, "finishes": ["glitter","holographic"],
          "topper": false, "clear": false, "coats": 1, "colours": ["pink"], "revision": "3f9a1c0b2d"}
Status   {"key": "sold_out", "label": "Sold out, retiring", "buyable": false}      // null for manual shades
ShadeRow {"id": 12, "title": "Spirit Fingers", "kind": "polish", "source": "holotaco", "is_topper": false,
          "price_cents": 1550, "compare_at_cents": null, "status": Status, "finishes": ["glitter","holographic"],
          "owned_count": 1, "wishlisted": false, "hero_image_url": "https://cdn.shopify.com/…",
          "released_on": "2021-06-18", "official_collection": "Rainbow Reflective",
          "marks": [[0,6],[7,14]], "tip": Tip}
          // marks: Unicode-scalar offsets into title (Python str indices); Swift indexes title.unicodeScalars
Bottle   {"id": 3, "shade_id": 12, "state": "half", "printed_code": "P259", "bought_on": "2026-07-21",
          "price_paid_cents": 1550, "opened_on": "2026-10-05", "notes": null, "archived": false,
          "created_at": "2026-07-21T10:02:11Z", "updated_at": "…"}
Layer    {"id": 7, "ord": 1, "shade_id": 44, "title": "One-Coat Black", "coats": 1, "label": "Base", "tip": Tip}
Tile     {"position": 12, "filled": true, "has_draft": false, "stack_id": 9, "draft_stack_id": null,
          "summary": "One-Coat Black + Flakie Holo Taco", "layers": [Layer], "painted_on": "2026-10-20", "note": null}
Wheel    {"id": 2, "slug": "k3m9xq", "name": "Holos", "slot_count": 20, "archived": false, "filled": 14, "drafts": 2,
          "tag_url": "https://polished.janpuc.com/w/k3m9xq", "created_at": "…"}
```

**Endpoints** (auth: Bearer unless marked public).

| Method | Path | Request → Response |
|---|---|---|
| GET | `/.well-known/apple-app-site-association` | public, `application/json`, no redirect: `{"applinks":{"details":[{"appIDs":["<TEAMID>.com.janpuc.polished"],"components":[{"/":"/w/*"},{"/":"/shades/new","exclude":true},{"/":"/shades/*"}]}]}}`; `POLISHED_APPLE_TEAM_ID` setting (empty → 404 and the route is off) |
| GET | `/auth/app/start` | browser, public; see 2.4 |
| GET | `/auth/app/finish` | browser, needs the web session; 302 `polished://auth?code=` |
| POST | `/api/v1/auth/exchange` | public; `{code, verifier, device_name, platform, app_version}` → `{token, token_id, user:{sub,name}}`; 400 `bad_code` |
| POST | `/api/v1/auth/revoke` | revokes the calling token → 204 |
| GET | `/api/v1/auth/devices` | `{items:[{id, device_name, platform, created_at, last_used_at, current}]}` |
| DELETE | `/api/v1/auth/devices/{id}` | 204 (also exposed on the web's More page as "Devices") |
| GET | `/api/v1/me` | `{user:{sub,name,first_name}, server:{version, public_url, store_url, timezone, over_black_available, shade_count}}` |
| GET | `/api/v1/home` | `{greeting_name, date, wear:{shade: ShadeRow, bottle: Bottle, worn_today: bool} \| null, recent:[{bottle: Bottle, shade: ShadeRow}] (6), wheel: Wheel+tiles \| null, counts:{bottles, shades, wished, wished_cents}}`; `?another=1` picks another owned shade (weighted away from the last 30 days) |
| POST | `/api/v1/wear/{shade_id}` | records today → `{worn_on}` (the `wear` table of web run 3; whichever run lands first adds `008_wear.sql`) |
| GET | `/api/v1/shades` | same params as `/shades` (`q, finish[], color[], collection, kind, status, owned, sort, page`) → `{items:[ShadeRow], total, page, has_more, fuzzy: bool}` (40 a page) |
| GET | `/api/v1/shades/facets` | `{finish:[], color:[], collection:[], official:[]}` |
| GET | `/api/v1/shades/{id}` | `{shade: ShadeRow, images:[url], tags:{finish,color,collection}, sku, handle, store_url, on_sale, bottles:[Bottle], wishlist:{id, priority, note} \| null, swatched_on:[{wheel_id, slug, name, position, stack_id}], tip_source:"override" \| "sampled" \| "none"}` |
| POST | `/api/v1/shades` | `{title, kind:"polish" \| "topper" \| "base"}` → the detail (201) |
| PUT | `/api/v1/shades/{id}/tip-colour` | `{hex:"#rrggbb"}` or `{hex:null}` → detail; 422 `validation` |
| GET | `/api/v1/bottles` | `?state&archived` → `{groups:[{shade: ShadeRow, bottles:[Bottle]}]}` |
| GET | `/api/v1/bottles/history` | `{years:[{year, count, total_cents, unpriced, months:[{month, label, count, total_cents, unpriced, rows:[{bottle: Bottle, shade: ShadeRow, dated_by_entry}]}]}]}` |
| POST | `/api/v1/shades/{id}/bottles` | `{state, printed_code, bought_on, price_paid_cents, opened_on, notes}` → `{bottle, learned:{code, previous_shade: ShadeRow \| null} \| null}` (201); 422 per field |
| PATCH | `/api/v1/bottles/{id}` | any subset of the same fields plus `archived` → Bottle |
| DELETE | `/api/v1/bottles/{id}` | 204 |
| GET | `/api/v1/wishlist` | `?max_priority=3` → `{items:[{id, shade: ShadeRow, priority, note, added_on, buyable}], summary:{count, total_cents, buyable_count, buyable_cents}, cart:{url \| null, total_cents, count, skipped, names:[…]}}` |
| PUT | `/api/v1/shades/{id}/wishlist` | `{priority:2}` → the item (existing item kept) |
| PATCH | `/api/v1/wishlist/{item_id}` | `{priority, note}` → the whole wishlist body |
| DELETE | `/api/v1/wishlist/{item_id}` | 204 |
| POST | `/api/v1/wishlist/bought` | `{items:[{id, price_cents \| null}], bought_on}` → `{bottles:[Bottle], wishlist: <body>}`; 404 unknown item, 422 |
| GET | `/api/v1/lookup` | `?q&via=scan \| typed` → `{outcome: match \| suggestion \| unknown_code \| unknown_printed \| invalid_code \| results, code, kind, shade: ShadeRow+images \| null, identifier_id, results:{items, total} \| null}` |
| POST | `/api/v1/identifiers` | `{kind, value, shade_id}` → `{identifier:{id, kind, value, shade_id}, created: bool, shade: ShadeRow}` |
| GET | `/api/v1/identifiers` | `{items:[{id, kind, value, shade: ShadeRow, use_count, created_at, last_used_at}]}` |
| DELETE | `/api/v1/identifiers/{id}` | 204 |
| GET | `/api/v1/wheels` | `?archived` → `{items:[Wheel+{tiles:[Tile]}]}` (tiles included: the list draws mini rings) |
| POST | `/api/v1/wheels` | `{name, slot_count}` → Wheel (201); 422 |
| GET | `/api/v1/wheels/{id}` and `/api/v1/w/{slug}` | `Wheel + {tiles:[Tile], filled_count, others:[{id, name, slug}]}`; unknown → 404 (after auth, as the web) |
| PATCH | `/api/v1/wheels/{id}` | `{name}` or `{archived}` → Wheel |
| DELETE | `/api/v1/wheels/{id}` | → `{deleted_swatches: 3}` |
| POST | `/api/v1/wheels/{id}/slug/regenerate` | → Wheel (new slug) |
| POST | `/api/v1/wheels/{id}/slug/take` | `{from_wheel_id}` → Wheel; 422 `same_wheel` |
| POST | `/api/v1/wheels/{id}/slots/{pos}/draft` | → Sheet (below), `resumed: bool` |
| DELETE | `/api/v1/wheels/{id}/slots/{pos}` | clear the swatch → 204 |
| GET | `/api/v1/stacks/{id}` | Sheet `{stack_id, wheel:{id, slug, name}, position, name, note, painted_on, layers:[Layer], summary, full, tip: Tip[] (the composite recipe = layers' tips in order)}` ; 409 `not_a_draft` |
| POST | `/api/v1/stacks/{id}/layers` | `{shade_id}` → Sheet; 422 `stack_full` |
| PATCH | `/api/v1/stacks/{id}/layers/{layer_id}` | `{coats_delta: ±1}` or `{move: "up" \| "down"}` → Sheet |
| DELETE | `/api/v1/stacks/{id}/layers/{layer_id}` | → Sheet |
| POST | `/api/v1/stacks/{id}/template` | `{kind:"over_black"}` → Sheet + `{result: added \| already \| unavailable}`; `{kind:"copy", source_stack_id}`; `{kind:"last"}` → Sheet (+ `result: nothing_saved`) |
| GET | `/api/v1/stacks/copy-sources` | `?q` → `{items:[{stack_id, wheel_name, wheel_slug, position, name, painted_on, summary, layers}]}` |
| GET | `/api/v1/stacks/pick` | `?q&scope=owned \| toppers \| all` → `{items:[ShadeRow], total, suggestion: ShadeRow \| null}` (the P-code suggestion row first) |
| POST | `/api/v1/stacks/{id}/save` | `{name, note, painted_on}` → `{wheel_id, position, tile: Tile}`; 422 `empty_stack` |
| POST | `/api/v1/stacks/{id}/cancel` | → `{wheel_id, position, tile: Tile}` |
| GET | `/api/v1/sync` | `{running: bool, last:{started_at, finished_at, status, trigger, counts…}, runs:[…10], cooldown_until}` |
| POST | `/api/v1/sync/run` | 202 `{run_id}`; 409 `sync_running`; 429 `cooldown` |
| POST | `/__test/reset` | **only** when `POLISHED_AUTH_MODE=none` and `POLISHED_TEST_RESET_FROM=<template.db>`; copies the template over the live DB; loopback only. For the UI-test harness |

Server-side files: new package `src/polished/api/` (`__init__.py` router, `auth.py` tokens, `schemas.py` pydantic models, `shades.py`, `bottles.py`, `wishlist.py`, `wheels.py`, `stacks.py`, `lookup.py`, `home.py`, `sync.py`), migration `008_api_tokens.sql` (`api_token(id, user_sub, user_name, device_name, platform, token_hash unique, created_at, last_used_at, revoked_at)`, `app_login_code(code_hash, user_sub, user_name, challenge, device_name, expires_at, used_at)`), `auth.py` gains the two browser routes and a Bearer branch in the gate (`/api/v1/` paths: Bearer or 401 JSON, never a redirect), `security.py` the Origin bypass, `server.py` one `include_router`. Domain modules are reused unchanged; the API serialises their dicts. Tests `tests/test_api_*.py` against the fixtures, plus a test that every fixture in `spec/api/fixtures/` validates against `openapi.yaml`.

---

## 4. The tip renderer port

### 4.1 One recipe, one list of paint operations, two engines

`tips.py` is split in two: `ops(layers) -> list[dict]` (the paint plan) and `svg(ops)` (today's markup). `render()` stays `svg(ops(layers))` and its tests stay; a new test pins the SVG output of the current fixtures before the split so nothing drifts. The Swift `TipPainter.ops(for layers: [TipShade]) -> [TipOp]` must produce an equal list. Fixtures: `spec/tips/cases.json` (`{"source":"tips.py@<sha>","cases":[{"name","layers":[TipShade…],"ops":[…]}]}`, about 30 cases: every finish alone, every finish as a topper, jelly over black, flakie over nothing, thermal with and without hex2, matte top, chrome + flakie, 8-layer stack, clear base alone, empty list) generated by `scripts/make_tip_fixtures.py`. Numbers in the IR are rounded to 3 decimals and compared with tolerance 0.001; colours are lowercase `#rrggbb`.

Op kinds (the SVG elements tips.py already emits, no more):
```jsonc
{"op":"rect","fill":{"kind":"solid","color":"#c72bb9"},"opacity":1}
{"op":"rect","fill":{"kind":"linear","x1":0,"y1":0.15,"x2":1,"y2":0.85,"stops":[[0,"#ff5fa2",0.11],…]},"opacity":1}
{"op":"rect","fill":{"kind":"radial","cx":0.5,"cy":0.42,"r":0.78,"stops":[[0.55,"#000000",0],[1,"#000000",0.18]]},"opacity":1}
{"op":"dots","color":"#f2a9d6","opacity":0.5,"circles":[[cx,cy,r],…]}
{"op":"star","cx":40.1,"cy":77.3,"size":3.2,"color":"#ffffff","opacity":0.9}
{"op":"polygon","points":[[x,y],…],"color":"#71ad44","opacity":0.63,"stroke":"#ffffff","stroke_opacity":0.35,"stroke_width":0.4}
{"op":"path","d":"M-8 150Q51 52 112 96L112 128Q51 84-8 176Z","color":"#…","opacity":0.75,"blur":3.5}
{"op":"ellipse","cx":66,"cy":30,"rx":6,"ry":15,"rotate":14,"color":"#ffffff","opacity":0.1}
```
Canvas 102×168, `slice` fit (SwiftUI: `.aspectRatio(102/168, contentMode: .fill)` inside the clip). The two v3 run-1 tweaks (dome edge `.24 → .18`, highlight ellipse `(70,34) → (66,30)`) must be in `tips.py` before the fixtures are generated; the fixture header records the commit.

### 4.2 The random generator: SplitMix64 in both engines (a change to `tips.py`)

CPython's `random.Random` is MT19937 plus CPython-specific `randbelow` rejection sampling; porting it bit-for-bit is possible but a trap for an agent. The spec therefore defines the generator, and `tips.py` adopts it in the same commit as the split (the only visible change: dust, glitter and flake positions move once; bump `revision()` with a `"r2"` salt so cached SVGs refresh):

```
TipRandom(seed: UInt64)           state = seed (the shade id)
next() -> UInt64: state &+= 0x9E3779B97F4A7C15; z = state
                  z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9; z = (z ^ (z >> 27)) &* 0x94D049BB133111EB; return z ^ (z >> 31)
random() -> Double  = Double(next() >> 11) * 0x1.0p-53
uniform(a, b)       = a + (b - a) * random()
below(n)            = Int(random() * Double(n))          (n < 2^20)
choice(seq)         = seq[below(seq.count)];  randint(a, b) = a + below(b - a + 1);  randrange(n) = below(n)
```
Python: `class TipRandom` (20 lines, masks with `& (2**64 - 1)`), used as `rng = TipRandom(shade.id)`; call order in `_paint` unchanged. `spec/tips/random.json` holds, for seeds 0, 1, 7, 259, 2**32+5, the first ten `random()` values and ten `below(1000)` values. If Jan prefers the web tips untouched, the fallback is an exact MT19937 port (init_by_array seeding, 53-bit `random()` from two draws, `getrandbits`-based `_randbelow`); the fixture test is the same either way.

### 4.3 Drawing in Swift

- `TipShape: Shape`: the CSS radius `50% 50% 38% 38% / 62% 62% 30% 30%`, i.e. top corners with radii (0.5 w, 0.62 h), bottom corners (0.38 w, 0.30 h), each corner a quarter ellipse (four cubic arcs, kappa 0.5523). Used for clip, the die-cut stroke and the contact shadow.
- `TipCanvas: View` = `Canvas { ctx, size in … }` drawing the ops scaled to `size` (102→w): `rect` → `ctx.fill(Path(CGRect), with: .color / .linearGradient(Gradient(stops), startPoint:, endPoint:) / .radialGradient(…, center:, startRadius: 0, endRadius: r·w))`, `dots` → one `Path` of ellipses per group, `star`/`polygon`/`path` → `Path` (an SVG path parser for the two fixed magnetic paths is 40 lines; or hard-code them as `Path` builders keyed by the op's `d`, since tips.py has exactly two), `blur` → `ctx.drawLayer { $0.addFilter(.blur(radius:)) … }`, `ellipse` with rotation via `ctx.rotate`. Rendered once per (recipe revision, size, colour scheme) into an image cache (`ImageRenderer` at 3×, LRU 300 entries) so lists scroll at 120 Hz; the hero, rack and ring tips draw live.
- `TipView(recipe, size: .s/.m/.l/.xl/.ring, light: .static/.live)` reproduces v3 §2.4 around the canvas: contact shadow (ellipse 76% wide, 16% tall at the foot, `ShadowInk` 26% light / black 55% dark, blur 4), die-cut edge (`Surface` 1.5 pt + 1 pt `ShadowInk` 18% + soft 8/18 drop), inside: `Mat` 1 pt inset stroke, `Rim` 1 pt top-left highlight, 2 pt bottom-right occlusion, then the light overlay in `.softLight`: radial pool at (50% + lx·40%, 50% + ly·40%) 60×40%, white 50%, and the 115° band (transparent 38%, white 35% at 48%, transparent 58%). Sizes (pt): s 28×46, m 40×66 (44×72 regular), l 72×118 (88×144 regular), xl 96×158 (120×197 regular), ring slot 38×62 (44×72 regular).

### 4.4 The native light: tilt-reactive specular and holo

`TipLightModel` (`@Observable`, one per app, in the environment): `lx, ly ∈ [-1, 1]`, default (-0.35, -0.55) = the v3 static light. `CMMotionManager` at 30 Hz (`deviceMotionUpdateInterval = 1/30`, `.xArbitraryZVertical`), reads `attitude.roll` and `attitude.pitch`, subtracts the attitude captured when the screen appeared (so "flat on the desk" and "held up" both start at the default light), clamps to ±20°, low-pass filters (α 0.18), maps to `lx = -0.35 + roll/20°·0.6`, `ly = -0.55 + pitch/20°·0.4`. Off, and frozen at the default, when `accessibilityReduceMotion`, `ProcessInfo.processInfo.isLowPowerModeEnabled` (observe `NSProcessInfoPowerStateDidChange`), `scenePhase != .active`, no motion hardware, or the simulator. Only views that asked for `.live` light subscribe: the Home hero, the rack, the shade-detail hero, the builder head and the ring slots (≤ 40). Rows are `.static`.

`TipLight.metal`, applied with `.layerEffect(ShaderLibrary.tipLight(.float2(size), .float2(light), .float(holo), .float(spec), .float(gloss)), maxSampleOffset: .zero)` to the painted layer only (never to chrome): samples the layer, adds a specular pool whose centre follows `light` (gaussian, radius 0.32 of width, strength `spec` 0.35 creme/jelly, 0.6 metallic/chrome/reflective, 0.45 glitter, 0 matte), adds for `holo > 0` (holographic 0.22, iridescent 0.14, flakie 0.1, toppers ×0.6) a rainbow band: hue = fract(0.9·(uv.x·cos θ + uv.y·sin θ) + 0.35·light.x), θ = 115°, width 0.28, blended as `screen` at `holo`, and multiplies by `gloss` (0 matte, 1 otherwise) the band part. Uniforms change at most 30×/s; the layer is re-rasterised by SwiftUI on uniform change, which is fine for ≤ 45 small layers on A-series GPUs; run 6 measures with Instruments (Core Animation FPS ≥ 110 on iPhone 18 Pro with the 20-slot ring moving; otherwise drop the ring to `.static` and keep the heroes live).

Parity: `spec/tips/cases.json` guarantees the paint; the light is native-only and is checked by screenshots (run 6 compares the hero at the default light against the web's `tip-xl` by eye).

---

## 5. Visual and interaction design

### 5.1 Three shells from one app, by size class only

| Shell | Where | Navigation | Overlays | Shade detail |
|---|---|---|---|---|
| **Compact** | iPhone; iPhone Duo outer (compact width); Split View and Stage Manager windows under regular width | `TabView` (Home, Shades, Bottles, Wheels, Wishlist) with `tabBarMinimizeBehavior(.onScrollDown)`; `NavigationStack` per tab; system bars (vertical on the Duo outer display automatically) | sheets with detents | push |
| **Regular, iPhone Duo inner** | regular width, `UIDevice` idiom phone | the same `TabView` (stays a tab bar on iPhone; whether `.sidebarAdaptable` ever yields a sidebar on the Duo inner display is unverified, so the design does not depend on it); Shades, Wheels and Bottles become `NavigationSplitView` (list + detail, as Mail does on the Duo); the wheel page uses `ArrangementView` (27.1) so the ring and the builder split across the fold | builder as `.inspector` (trailing, 360–400 pt) or, partially folded, the secondary pane | the detail column |
| **Regular, iPad** | iPad, any window ≥ regular | `TabView.sidebarAdaptable` → sidebar with the five sections, Settings at its foot; `NavigationSplitView` in Shades, Wheels, Bottles | `.inspector` for the builder and the edit forms; sheets `presentationSizing(.form)` for create/confirm | the detail column; `?hl` highlight on the ring |

Rules: never branch on the device model; read `horizontalSizeClass` and the container width (`containerRelativeFrame`). Every layout must survive 320 pt wide (Split View one-third) and 1366 pt (13" landscape). No fixed widths except tips and the ring. Vertical bars on the Duo come for free from `NavigationStack` + `.toolbar`; the builder's Save lives in `ToolbarItem(placement: .confirmationAction)` and Cancel in `.cancellationAction` so the system places them (vertically on the outer display). Custom bottom bars are forbidden for that reason.

**iPhone Duo specifics (27.1 APIs behind `#available`).** The wheel screen reads `proxy.reservedRegions(kind: .division)`; when a division is active (partially folded, laptop or book pose) the `ArrangementView(.split)` puts the **ring on the upright half** and the **builder or the swatch list on the flat half**, which is the pose she will use at the desk with the real wheel in hand. Fully open: ring left, builder right. Grids (the Wheels list) use two or four columns, never three, so the fold falls between items (HIG). Nothing custom sits under the outer camera: all top chrome is system toolbar. `presentationPlacement(.trailing)` on the builder sheet when the inner display is open and no inspector is used.

### 5.2 Screen map

| Screen | Compact | Regular (iPad; Duo inner where noted) |
|---|---|---|
| Home | one column: greeting, search field (taps into Shades search), Wear today hero, Recently added rack on the ledge, wheel card (ring 132), Collection numbers, three links; a Scan toolbar button | two columns from 700 pt: hero and rack left; wheel card, collection and links right; max width 1120 centred |
| Shades | `.searchable` (placement automatic, `searchToolbarBehavior(.minimize)`), filter button with count badge → sheet (compact) / popover (regular), rows, Load more as the list's last row | list column 360–420; detail column; selected row `Fill` |
| Shade detail | hero plate (`Velvet` in dark), photo strip 3:4 snap, Fraunces title, meta line, Add bottle (filled) + heart, Bottles group, facts, Swatched on, Tip colour disclosure, store link | the same, two photos per row on wide; Add bottle in the toolbar as well |
| Bottles | Collection / History segmented in the title bar; level chips; groups | groups in two columns from 900 pt; the edit form as an inspector |
| History | years and months, totals in the section footers | months in two columns |
| Wishlist | head: "$78.50 for 5 shades in stock", Open in Holo Taco checkout (filled; opens `SFSafariViewController`), Copy list, I bought these; include segmented; rows by priority with swipe actions (priority menu, remove) | rows left; the bought flow as an inspector |
| Wheels | title + `+` (sheet: name, slot count stepper 1–40), cards with mini rings, archived in a collapsed section | 2 or 4 column grid; detail column holds the wheel |
| Wheel | ring, Swatches list, foot: Tag and QR, Rename, Archive, Delete (red) | ring + builder side by side (`ArrangementView` on Duo, `HStack` elsewhere) |
| Builder | sheet, detents `.medium` + `.large`, opens at `.large`, background interaction up through `.medium` | inspector 360–400 pt (iPad), fold pane (Duo) |
| Scan | full-screen cover: VisionKit view, framing guide, torch, Close, a text field "Type the digits, a P code, or a name" under it, result card, Learned codes link | centred 480 pt viewfinder, result beside from 1000 pt |
| Tag | QR 216 pt on `Surface` radius 20, the address with Copy, **Write to sticker** (filled; hidden on iPad and under "Designed for iPad"), Check the sticker, Move the tag (New tag URL, Take the tag of…), last written date | same, "Write it from your iPhone" lede when NFC is unavailable |
| Settings | (More on compact: the Home mark and the sidebar foot) Signed in as, Server, Devices, Catalog sync (status, Sync now), Learned codes, Add a shade by hand, Sign out, version | a sheet `presentationSizing(.form)` |
| Sign-in | the mark, "Polished", one filled button "Sign in with Pocket ID", the server name in `Ink3`, errors inline | centred 420 pt |

### 5.3 Wireframes

Home, iPhone 390 pt (compact):
```
Good evening, Nikola                              [mark]   ← Fraunces 34, SF 15 date under
Sunday 26 October
[ ⌕  Search 372 shades                            ] [▣]   ← field opens Shades search; ▣ scan
Wear today
┌──────────────────────────────────────────────────────┐
│ ▐▓▓▓▌  Acid Drip                                     │   ← tip-xl, live light; Fraunces 28
│ ▐▓▓▓▌  Holographic, metallic, shimmer                │
│ ▐▓▓▓▌  P12, half left                                │
│ [ I wore this          ]   Another                   │   ← one filled action
└──────────────────────────────────────────────────────┘
Recently added                             All 9 bottles ›
  ▐▓▌    ▐▓▌    ▐▓▌    ▐▓▌    ▐▓                            ← rack: tip-l, snap, pitch 88, peek 24
  Herb   Cast   Retina Spirit Ov…
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ← ledge 1.5 pt Line, shadows rest on it
Wheels                                            All 2 ›
┌ (◌ ring 132)  Holos                                  ┐
│                14 of 20, 2 drafts                    │
└──────────────────────────────────────────────────────┘
Collection
┌   9            8            6                        ┐   ← Fraunces 28 tabular
│   bottles      shades       wished, $87.50           │
└──────────────────────────────────────────────────────┘
Browse all shades ›   Toppers ›   New and in stock ›
[ ⌂ Home  ◊ Shades  ▯ Bottles  ◎ Wheels  ♡ Wishlist ]     ← system glass tab bar, minimises on scroll
```

Home, iPhone Duo outer (compact width, wider than tall): identical column; the system moves the tab bar and toolbar to the trailing edge, so the content column is narrower (about 300 pt): the rack shows three and a peek, the Collection numbers stack 2 + 1.

iPhone Duo inner, fully open (regular width), Wheels tab:
```
│ Wheels            [+] │ Holos                                        ⋯ │
│ (◌) Holos  14 of 20   │                 ( ring, radius to fit 390 )     │
│ (◌) Toppers 6 of 20 ▸ │                     ◌ 14                        │
│                       │                    of 20                        │
│                       │ Swatches                                        │
│                       │  12 ▐▓▌ One-Coat Black + Flakie Holo Taco  20 Oct│
│ ⌂ ◊ ▯ ◎ ♡  (tab bar)  │  13 ▐▓▌ Spirit Fingers ×2                       │
```
Partially folded like a laptop (division active): the ring takes the upright half, the Swatches list or the open builder the flat half; nothing crosses the fold.

Wheel ring + builder, iPad 13" landscape:
```
│ ▌Polished     │ Holos                                           [Tag] [⋯] │ Slot 12                 Cancel  Save │
│  ⌂ Home       │                                                           │ ▐▓▓▓▌ One-Coat Black + Flakie Holo…  │
│  ◊ Shades     │               ( ring radius 150, slots 44×72 )            │ Base  ▐▓▌ One-Coat Black   − 1 +  ↑↓ × │
│  ▯ Bottles    │                       ◌ 14                                │ Top   ▐▓▌ Flakie Holo Taco − 1 +  ↑↓ × │
│  ◎ Wheels     │                      of 20                                │ [Over black] [Copy from…] [Same as last]│
│  ♡ Wishlist   │ Swatches                                                  │ [ ⌕ Search shades or a P code     ] [▣] │
│               │  12 ▐▓▌ One-Coat Black + Flakie Holo Taco      20 Oct     │ (Owned) (Toppers) (All)                 │
│  ⚙ Settings   │  13 ▐▓▌ Spirit Fingers ×2                                 │  ▐▓▌ Spirit Fingers            glitter + │
│               │ Tag and QR · Rename · Archive · Delete                    │  ▐▓▌ Thirst Trap                creme  + │
```

Builder sheet, iPhone (detent `.large`; at `.medium` only the head and the layers show, the ring behind stays tappable):
```
━━
▐▓▓▓▌  Slot 12                                        Cancel
▐▓▓▓▌  Holos · Resumed your draft                           ← tip-xl composite, live light
▐▓▓▓▌  One-Coat Black + Flakie Holo Taco
Base  ▐▓▌ One-Coat Black        −  1  +     ↑ ↓   ×
Top   ▐▓▌ Flakie Holo Taco      −  1  +     ↑ ↓   ×        ← 2 pt rail through the tips
[ Over black ] [ Copy from… ] [ Same as last ]
[ ⌕ Search shades or a P code                     ] [▣]
( Owned ) ( Toppers ) ( All )
  ▐▓▌ Spirit Fingers        Glitter, holographic       +
  ▐▓▌ Thirst Trap           Creme                      +
▸ Name and note                                               ← disclosure
Painted on  [ Today  26 Oct 2026 ▾ ]  (Today) (Yesterday)
[ Save swatch                                       ]         ← ToolbarItem .confirmationAction, glass bar
```
Three taps add three layers; the field keeps focus after a tap (`@FocusState` re-set in the same transaction, which native SwiftUI allows where Safari did not).

Scan, iPhone:
```
┌──────────────────────────────────────────────┐
│            live camera, 4:3 crop             │  ← DataScannerViewController
│         ┌────────────────────┐               │
│         │   framing guide    │               │   guide flashes on accept
│         └────────────────────┘               │
│  [torch]                             [Close] │  ← GlassEffectContainer: the only custom glass
└──────────────────────────────────────────────┘
Point at the barcode under the bottle
[ Type the digits, a P code, or a name           ]
┌ result ──────────────────────────────────────┐
│ [photo 72×96] ▐▓▓▌ Spirit Fingers            │
│               Glitter, holographic   $15.50  │
│ [ Add bottle ]         This isn't it         │
└──────────────────────────────────────────────┘
Learned codes ›
```
Outcomes map to the web's: `match` (card, Add bottle, This isn't it), `suggestion` ("P259 was Spirit Fingers on a bottle you added before", Use it, plus results), `unknown_code` ("New barcode. Which shade is this?" + picker; choosing learns then opens Add bottle), `unknown_printed` (picker; the code rides into the bottle form), `invalid_code` ("Couldn't read that reliably. Try again."), `results`.

Tag, iPhone (the NFC flow end to end):
```
Tag and QR code
A sticker on the wheel opens it here. Write the link once; move it any time.
┌──────────────┐
│   QR 216 pt  │   CoreImage CIQRCodeGenerator, correction M, Ink on Surface, radius 20
└──────────────┘
https://polished.janpuc.com/w/k3m9xq            Copy
[ Write to sticker                               ]   ← filled; hidden when NFCNDEFReaderSession.readingAvailable is false
Check the sticker
Written 26 Oct 2026, 18:42                            ← local record per slug; "Not written yet" in Ink3
Move the tag
  New tag URL        (red text; confirms: "The old sticker will stop working.")
  Take the tag of…   (sheet listing the other wheels)
```
Write flow: `NFCNDEFReaderSession(delegate:queue:nil, invalidateAfterFirstRead: false)`, `alertMessage` "Hold the sticker to the top of your iPhone." → `readerSession(_:didDetect tags:)`: more than one tag → `alertMessage` "One sticker at a time." and `restartPolling()`; else `connect(to:)` → `queryNDEFStatus`: `.notSupported` → `invalidate(errorMessage: "This sticker can't hold a link.")`; `.readOnly` → "This sticker is locked. Use another one."; `.readWrite` with capacity < payload → "This sticker is too small." (the URI record is about 35 bytes; NTAG213's 144 bytes are plenty); else `writeNDEF(NFCNDEFMessage(records: [NFCNDEFPayload.wellKnownTypeURIPayload(url:)!]))` → success: `alertMessage` "Done. Tapping this sticker opens Holos.", `invalidate()`, `.success` haptic, the page records the date. Never `writeLock`. Errors: `.readerSessionInvalidationErrorUserCanceled` silent; `…SessionTimeout` → inline "Nothing was written. Try again and hold still."; `…FirstNDEFTagRead` not applicable; other `NFCReaderError` → inline "Couldn't write the sticker (<code>). Try again." Check the sticker: a read session (`invalidateAfterFirstRead: true`) that compares the first URI record with the tag URL and says "This sticker opens Holos" or "This sticker opens something else: <host/path>" (with "Write it again"). First-time explanation is the page's lede; iOS supplies the system NFC sheet, so no onboarding screen. After writing, the device-side proof is a tap on the sticker with the app closed: background tag reading shows the notification, the universal link opens the app on the wheel (verified in Apple's background-reading doc: a universal link in the first URI record launches the associated app; Safari only when no app matches).

### 5.4 Materials: Liquid Glass on chrome only

System components carry the glass: tab bar, sidebar, navigation and tool bars, search field, sheets' chrome, popovers, menus, alerts. Content never gets `glassEffect`: not tips, not cards, not the ring, not rows. The only custom glass is the `GlassEffectContainer` with the torch and Close buttons over the camera (`glassEffect(.regular.interactive(), in: .circle)`), because there it is chrome over live content. No custom backgrounds behind bars (`toolbarBackground` untouched), so the scroll edge effect works; `scrollEdgeEffectStyle(.soft, for: .top)` on the Home shelf. Groups keep the 1 pt ring edge, no card shadows; tips cast the contact shadow. Reduce Transparency is the system's job for its glass; our camera buttons use `.regular` glass which the system frosts.

### 5.5 Typography

- **Fraunces144pt-SemiBold.ttf** (static instance, SIL OFL 1.1, from the Fraunces repo `fonts/ttf/`; it bakes in `opsz 144`, `wght 600`, SOFT 0, WONK 0, exactly the v3 cut). Four roles only: Greeting (`Font.custom("Fraunces144pt-SemiBold", size: 34, relativeTo: .largeTitle)`, 40 on regular), Shade title (28, `.title`), Wheel name (22 cards, 34 page), Hub and Collection numbers (56 on the ring, 28 on Home; tabular via `UIFontDescriptor` feature `kNumberSpacingType / kMonospacedNumbersSelector`; run 1 checks Fraunces exposes `tnum` and otherwise right-aligns digits in fixed-width frames). Never below 22 pt, never in rows, buttons, labels, chips or tabs. Dynamic Type: the roles scale with their text style but are capped at ×1.35 (`dynamicTypeSize(...DynamicTypeSize.xxxLarge)` on those views only) so the greeting holds one line.
- **SF Pro** for everything else through system text styles (`.body` 17, `.subheadline` 15 for finishes and status, `.footnote` 13 for dates and ×N, `.caption` 12 for layer labels, `.headline` for row names). `monospacedDigit()` on prices, counts and dates. Sentence case; no eyebrows, no caps labels, no middle dots.

### 5.6 Colour

Asset catalog colour sets with Any/Dark and High Contrast variants, from v3 §2.2: `Board #f7f3f2/#160b14`, `Surface #fefcfb/#20131d`, `Fill #efe8e6/#30212c`, `Fill2 #e6dcd9/#3a2b36`, `Line #e3dad8/#372834`, `Line2 #c9bcb9/#4d3c49`, `Ink #2a1623/#f7eff5`, `Ink2 #6e5a63/#b7a4b2`, `Ink3 #8f7d86/#92808d`, `Primary #381531/#f7eff5`, `PrimaryOn #ffffff/#280c23`, `Heart #d83486/#ff77b4`, `OK #007840/#61da92`, `Warn #975800/#f9b64f`, `Bad #be222a/#ff7f7f`, `Velvet (dark only) #0f070e`, `ShadowInk rgb(40,20,30)/black`. High contrast: `Line`→`Line2` values, `Line2` darker (`#9d8e8b`/`#6a5866`), `Ink2`→`Ink`. The app tint is `Ink`; `Primary` fills the one filled action per screen; `Heart` is the wishlist only; status words are text colour only. The foil conic gradient is used only for the `?hl` ring on tips, the save sweep and the logo. Backgrounds: `Board` behind everything, `Surface` for grouped content, the hero plate `Velvet` in dark.

### 5.7 Motion

Springs, interruptible, from the current value (apple-design skill). Defaults `.smooth(duration: 0.3)` for routine state, `.snappy` for selections, `.bouncy(extraBounce: 0.1)` only after a gesture with momentum. Named moments:
1. **Press**: `scaleEffect(0.96)` while pressed (custom `ButtonStyle`), rows wash `Fill` at once.
2. **Tip to detail**: `navigationTransition(.zoom(sourceID: shade.id, in: tips))` with `matchedTransitionSource` on the row tip, the rack tip and the ring slot; the detail's hero tip is the target. Reduce Motion: the system crossfades.
3. **Add to collection** (the authored moment, 600 ms): the new bottle row's tip arrives with a `KeyframeAnimator` on scale (0.85 → 1.04 at 30% → 0.98 at 45% → 1) and opacity, plus one specular sweep (the band's offset from −60% to 160% over 700 ms) via `TipView(sweep:)`. The same sweep on a saved ring slot and on the Home hero after Another. `.impact(.medium)` haptic on landing.
4. **Sheets**: system presentation; builder detents as in 5.2; `presentationDragIndicator(.visible)`.
5. **Ring tap**: slot scales to 1.08 for 120 ms, then the sheet.
6. **Fold and resize**: nothing animates on a size-class change beyond the system's; the ring re-lays out with `.animation(nil)` so it never swims.
Reduce Motion: no scale, no sweep, no tilt; opacity only, 150 ms. Nothing animates on first appearance except the arrival moment when it is caused by her action.

### 5.8 Haptics map (`sensoryFeedback`)

| Event | Feedback |
|---|---|
| Segment, level chip, priority, detent change, ring slot focus | `.selection` |
| Layer appended; coats ±; move | `.impact(weight: .light)` |
| Bottle added (arrival lands); swatch saved; tag written; bought | `.success` |
| "This isn't it"; a code already known to another shade; nothing saved for Same as last | `.warning` |
| Write failed; save refused (empty stack); network failure on a write | `.error` |
| Barcode accepted | `.impact(weight: .rigid)` (the guide flashes on the same frame) |
No haptic on scroll, on navigation or on the NFC detection itself (iOS plays its own).

### 5.9 Empty states and copy

One line and one action, the unpainted drawing where the thing will appear: Home without bottles ("Scan a bottle", unpainted `tip-xl`), no wheel (unpainted ring, "Make one"), no results (`Nothing matches "overstim". Try fewer letters.` and "Add it by hand"), empty wishlist ("Nothing wished yet. Tap the heart on a shade."), empty history, no learned codes, offline ("Showing what was here a moment ago" status line under the title, never a blocking page), signed out (section 5.2). Copy voice is the web's (VISUAL.md §9).

### 5.10 Accessibility

- VoiceOver: tips are decorative in rows (`accessibilityHidden`) and the row carries one label: "Spirit Fingers, glitter, holographic, wished, owned twice, $15.50". Bottle rows: "Spirit Fingers, P259, half left, bought 21 July 2026, $15.50". Ring slots are buttons: "Slot 12, One-Coat Black + Flakie Holo Taco, painted 20 October" / "Slot 3, empty" / "…, draft in progress". The hero: "Wear today: Acid Drip, holographic, metallic, shimmer, half left". The wheel's hub is one element: "14 of 20 slots filled". Rotor actions on rows: wishlist, level, remove.
- Dynamic Type: every SF text style scales; rows switch to a vertical layout at accessibility sizes (`dynamicTypeSize.isAccessibilitySize`); tips keep their size; the ring's slot numbers hide at AX sizes and VoiceOver carries them.
- Differentiate without colour: status and level always have words; the heart has a filled/outlined state; the `?hl` ring is accompanied by "Swatched here" in the slot label.
- Reduce Motion and Transparency as above; Increase Contrast via the asset variants; minimum hit size 44 pt everywhere (ring slots get an invisible 44×72 hit rect).
- Keyboard on iPad: `/` focuses search, `⌘N` Add bottle on a shade, arrows move list selection, `⎋` closes the inspector (`.keyboardShortcut`, `focusable`).

### 5.11 App icon

Source: `src/polished/static/icons/logo.svg`. Run 1 ships a flattened 1024 px `AppIcon` rendered from it (`scripts/make_icons.py` already rasterises; add a 1024 output), which iOS 26/27 wraps in glass automatically. For the layered Liquid Glass icon, the agent exports four layer SVGs from `logo.svg` into `app/Design/icon-layers/` (ground, finger, nail foil + sheen + dome, sparkle + lunula), and Jan spends ten minutes in Icon Composer (Xcode → Open Developer Tool) importing them and saving `app/Polished/Polished.icon`; adding the `.icon` file to the target replaces the asset catalog icon (Apple's Icon Composer doc). Keep the sparkle inside the safe area; the finger bleeds off the bottom by design.

---

## 6. Testing without a device

### 6.1 Swift Testing (`PolishedCoreTests`, runs in `xcodebuild test` and in `swift test` inside `app/PolishedCore`)

- **Renderer parity**: for every case in `spec/tips/cases.json`, `TipPainter.ops(for:)` equals the recorded ops (same count, same kinds in order, numbers within 0.001, colours equal). `TipRandom` against `spec/tips/random.json`.
- **TipShape**: path bounding box equals the frame; symmetric about the vertical axis.
- **Decoding**: every file in `spec/api/fixtures/` decodes into its DTO with a `JSONDecoder` whose unknown keys are collected (a custom `userInfo` key-tracking decoder) and the test fails on an undecoded top-level key, so contract drift surfaces here first. Errors decode into `APIError`.
- **Normalisation**: `spec/identifiers/gtin.json` and `printed.json` vectors (the GTIN check digit, the 14-digit rule, `259 → P259`).
- **Marks**: `AttributedString` highlighting from `marks` on titles with `™`, accents and combining marks (`spec/api/fixtures/shades-search-*.json` carry marks from the server).
- **Deep links**: `/w/k3m9xq` → wheel route; `/w/K3M9XQ`, `/w/../x`, `/shades/abc` → rejected.
- **Light model**: roll 0 / pitch 0 → default light; ±40° clamps to ±20°; Reduce Motion freezes.

### 6.2 XCUITest flows mirroring `tests/e2e/run_flows.py`

The app under test talks to **the real server, locally**: `app/Scripts/flows.sh` seeds a template DB with `uv run python tests/e2e/flows/seed.py`, starts `polished serve` with `POLISHED_AUTH_MODE=none POLISHED_PUBLIC_URL=http://127.0.0.1:8080 POLISHED_TEST_RESET_FROM=<template>`, and launches the app with `-server http://127.0.0.1:8080 -token dev -uitest 1` (DEBUG builds only honour these). Each test's `setUp` posts `/__test/reset`, so flows never see each other's data, exactly like the web harness. No URLProtocol stubs: the contract is exercised end to end. `FixtureAPI` exists only for previews and widget tests.

Flows (one XCTestCase each, steps named like the web's, a screenshot attachment per step with `lifetime = .keepAlways`):
`search` (exact title first, "magentic taco" fuzzy with marks, "onecoat", accents, no match → Add it by hand), `add-bottle` (shade → Add bottle sheet → level, date presets, price → arrival), `bottle-level` (half → low → empty → archived under Past bottles), `wishlist` (heart, priority, checkout link present, I bought these → bottles, item gone, History shows it), `builder` (wheel → slot 12 → Over black → search "flak" → add → coats + → Save swatch → tile filled, Swatches row), `wheel-delete` (Delete → confirmation sheet → gone, status line), `history`, `tabs` (every tab and Settings once), `scan-typed` (the Scan screen's field: `259` → suggestion; `810170284120` → unknown code → learn → Add bottle), `tag-page` (QR shown, address, Write hidden on simulator with the lede, Check hidden), `deep-link` (`xcrun simctl openurl booted https://polished.janpuc.com/w/<slug>` → the wheel; needs the Debug `?mode=developer` association, else the test launches the app with `-open <url>` and exercises the router), `signin` (the sign-in screen renders; the session itself is device-only).

Destinations and schemes: `platform=iOS Simulator,name=iPhone 18 Pro`, `name=iPhone Duo`, `name=iPad Pro 13-inch (M5)`; light and dark (`xcrun simctl ui <udid> appearance dark` before the run), plus one extra pass on the iPhone at `-UIPreferredContentSizeCategoryName UICTContentSizeCategoryAccessibilityL` and one with `increase_contrast enabled`. **iPhone Duo folded versus unfolded:** the device type exists; the simulator's default pose and any command-line pose switch are not documented in `simctl` (no `fold`/`pose` subcommand in Xcode 27.1's help). Run 2 checks Device Hub's "Configuring the environment of a simulated device" and `xcrun simctl help` for a pose control and records what it finds; until then the Duo run covers whatever the default pose is and Jan covers the other on the device.

Report: `xcodebuild test … -resultBundlePath out.xcresult`, then `xcrun xcresulttool export attachments --path out.xcresult --output-path shots/` (`manifest.json` maps files to tests), and `app/Scripts/report.py` writes `~/.cache/polished/native-flows/<timestamp>/index.html` in the style of `tests/e2e/flows/report.py` (grid: flow × device × scheme, step names, pass/fail, the screenshots). Exit 1 on any failure. The runtime must be installed first: `xcodebuild -downloadPlatform iOS`.

### 6.3 Device-only, with the manual checklist for Jan

Cannot run on a simulator: Core NFC (write, check, background tag read), the camera (live scan), universal links from a real tap (Safari, Messages, NFC, the Camera app's QR), haptics, Core Motion tilt light, Low Power Mode behaviour, the Duo's real poses and Split View, TestFlight install, Pocket ID passkey sign-in.

Checklist (iPhone, after the first TestFlight build): (1) install from TestFlight, sign in with the passkey, land on Home with the greeting; (2) Shades → Spirit Fingers → the zoom, the tilt light moves with the phone, Reduce Motion stops it; (3) Scan the Spirit Fingers bottle (`810170284120`) → unknown code → pick it → Add bottle → the arrival moment and haptic; scan again → match; (4) Wheels → Holos → Tag → Write to sticker → Done; Check the sticker → "opens Holos"; (5) close the app, tap the sticker → notification → the app opens on Holos; repeat with the app in the background and with the app force-quit; (6) delete the app, tap the sticker → Safari opens the wheel; reinstall; (7) scan the QR with the Camera app → the app opens; (8) tap `https://polished.janpuc.com/w/<slug>` in Messages → the app; `/shades/<id>` → the app; `/wishlist` → Safari; (9) Mac Safari: the same links open the web, not an app; (10) Settings → Devices lists both phones; Sign out revokes; the web's Devices page shows the revocation; (11) iPhone Duo: Home closed, open it mid-scroll (state kept), rotate, Split View with Safari beside Polished, the wheel page partially folded (ring upright, builder flat); (12) Low Power Mode: light freezes; (13) widget: add Wear today, tap it → the shade; (14) `curl https://app-site-association.cdn-apple.com/a/v1/polished.janpuc.com` returns the AASA (Apple's CDN fetched it through the Cloudflare tunnel).

---

## 7. Distribution

- **TestFlight, internal testing.** Internal testers must be App Store Connect users; the roles allowed are Account Holder, Admin, App Manager, Developer or Marketing (Apple's "Add internal testers" help, read today). Invite Nikola as a user with the **Marketing** role, restricted to this one app: the least privileged role that can test, no access to builds, certificates or finances. Internal builds skip Beta App Review, reach testers within minutes of processing and expire after 90 days; 100 testers max. External testing by email would need the one-time Beta App Review for the first build and gains nothing here, so no.
- **App record** (Jan, in App Store Connect): New App → iOS, name "Polished" (App Store Connect names are unique across the store; if taken, "Polished Nails" or "Polished by janpuc"; the name on the Home Screen is `CFBundleDisplayName` "Polished" regardless), primary language English, bundle ID `com.janpuc.polished`, SKU `polished-ios`. Do **not** tick "Make available on Mac" (section 1).
- **Signing:** automatic; the first `xcodebuild -allowProvisioningUpdates` with the API key registers the App ID with NFC Tag Reading, Associated Domains and App Groups and creates the profiles. If a capability refuses to auto-enable, Jan adds it under Certificates, Identifiers & Profiles → Identifiers → `com.janpuc.polished`.
- **App Store Connect API key** (Jan): Users and Access → Integrations → Team Keys → generate, role **App Manager** (upload needs Developer or higher; App Manager also lets a later script manage groups), download `AuthKey_<KEYID>.p8` once, store the file, key ID and issuer ID in 1Password (item "App Store Connect API key, polished"). The script reads them with `op read` into `~/.appstoreconnect/private_keys/` (altool's and xcodebuild's expected location) for the duration of the upload.
- **Upload from the CLI** (`app/Scripts/archive-upload.sh`): `xcodegen generate` → `Scripts/bump-build.sh` → `xcodebuild -project app/Polished.xcodeproj -scheme Polished -configuration Release -destination 'generic/platform=iOS' -archivePath build/Polished.xcarchive archive -allowProvisioningUpdates -authenticationKeyPath … -authenticationKeyID … -authenticationKeyIssuerID …` → `xcodebuild -exportArchive -archivePath build/Polished.xcarchive -exportOptionsPlist app/ExportOptions.plist -exportPath build/export -allowProvisioningUpdates -authenticationKey…` with `ExportOptions.plist` `{method: app-store-connect, destination: upload, signingStyle: automatic, teamID: <TEAMID>, uploadSymbols: true, manageAppVersionAndBuildNumber: false}`. Verified today: Xcode 27.1's `xcodebuild` documents `-exportArchive`, `-exportOptionsPlist`, `-allowProvisioningUpdates` and the three `-authenticationKey*` flags; `xcrun altool --upload-app -f build/export/Polished.ipa -t ios --apiKey <KEYID> --apiIssuer <ISSUER>` still ships (altool 1.1.3) and Apple's "Upload builds" help still lists altool and Transporter as upload paths, so it is the fallback if the export-and-upload step fails. `notarytool` is for Mac notarisation and is not involved. Processing takes 5 to 20 minutes; with the internal group's "Enable automatic distribution" ticked the build reaches both phones without another click.
- **Build numbering:** `MARKETING_VERSION` 1.0.0 (bumped by hand per milestone), `CURRENT_PROJECT_VERSION` = `date -u +%Y%m%d%H%M` at archive time (monotonic, unique per minute, 12 digits), both stamped into the Settings version row ("1.0.0 (202610261842)").
- **What Jan clicks himself:** accept the current Program License Agreement; create the app record; generate the API key into 1Password; invite Nikola (Marketing, one app) and confirm she accepts the email and installs TestFlight; create the internal group "Household" with automatic distribution and add both; enable Developer Mode on both phones (and "Associated Domains Development" on his for Debug builds); install the first build; run the checklist of 6.3; later, Icon Composer (5.11). Everything else is scripted.

---

## 8. Staged implementation plan

Each run is one agent, ≤ 90 minutes, ends with a build that passes `xcodebuild test` on the iPhone 18 Pro simulator and the flows report for its flows (from run 2 on), and stops. The orchestrator commits (`feat(app): …`, `feat(api): …`, `build(app): …`).

**Prerequisites (Jan, before run 1):**
1. `xcodebuild -downloadPlatform iOS` (the iOS 27.1 simulator runtime; nothing boots without it) and `brew install xcodegen`.
2. Team ID into `app/Team.xcconfig` (the orchestrator creates the file from the template).
3. App Store Connect: app record, API key in 1Password, Nikola's invitation (section 7). Needed by run 6, not before.
4. Confirm Nikola's iPhone model and iOS version (decides whether the deployment target becomes 27.1).
5. The greeting time zone (already pending from the v3 spec) and whether the `tips.py` dust may move once (section 4.2; default yes).
6. NFC stickers: NTAG213 or larger, 144 bytes is plenty.

**Server runs (the API worker; its files are `src/polished/api/`, `spec/`, `tests/test_api_*.py`, `scripts/make_api_fixtures.py`, `scripts/make_tip_fixtures.py`, one migration, and single-line touches in `server.py`, `auth.py`, `security.py`; the web runs own `templates/`, `static/`, `routes/`, `web.py`):**
- **S0 (30 min, first, before web run 1 or inside its brief since both edit `tips.py`):** split `tips.py` into `ops()` + `svg()`, `TipRandom` (SplitMix64), the two v3 tweaks, `revision()` salt `r2`, `scripts/make_tip_fixtures.py`, `spec/tips/cases.json`, `spec/tips/random.json`, `spec/identifiers/*.json`; tests pass; the SVG for the pinned cases is byte-identical before and after the split (apart from the RNG change, which has its own test).
- **S1 (90 min):** Bearer gate, `008_api_tokens.sql`, `/auth/app/*`, `/api/v1/auth/*`, `/me`, `/home`, `/shades*`, `/bottles*` (GET), `/wishlist` (GET), `/wheels*` (GET), `/w/{slug}`, `/stacks/{id}` (GET), `/lookup`, `/identifiers` (GET), `/sync` (GET), the AASA route with `POLISHED_APPLE_TEAM_ID`, `/__test/reset`, `spec/api/openapi.yaml`, fixtures export, tests.
- **S2 (90 min):** every write endpoint of section 3, `/wear/{id}` (with `008_wear.sql` or `009` depending on web run 3), the web More page's Devices list, tests, fixtures for every write response. The deploy (image release, `POLISHED_APPLE_TEAM_ID` in the HelmRelease env) is Jan's after S2.

**App runs:**
1. **Skeleton and the painted tip** (needs S0): `project.yml`, targets, entitlements, Info.plist, `Team.xcconfig`, asset colours, Fraunces, `NailTips` (TipRandom, TipPainter, TipCanvas, TipShape, TipView with the static v3 light, LevelArc, Ledge, Rack, Ring geometry), the tab shell with placeholder screens showing fixture tips, the 1024 icon; Swift Testing: renderer parity, random vectors, GTIN vectors. Check: `xcodebuild test` green on iPhone 18 Pro; a debug gallery screen shows the 30 fixture tips at four sizes in light and dark (screenshot into the report dir).
2. **Reading the collection** (needs S1 deployed or run against a local server): `PolishedAPI`, `LiveAPI` with ETags, `PolishedStore` snapshots, Session + Keychain + `ASWebAuthenticationSession` flow, Router and deep links, Home, Shades (search, marks, filters, Load more), Shade detail with the zoom transition, Bottles + History, Wishlist (read), Wheels list + the ring page (read), Settings; the flows harness (`flows.sh`, `report.py`, `/__test/reset`) with `search`, `tabs`, `history`, `deep-link`; the Duo pose investigation note. Check: flows green on the three simulators, light and dark.
3. **Writes** (needs S2): Add/edit bottle sheet (level, date presets, price, P code under More details), level chips, archive and delete, wishlist heart, priority, note, remove, checkout (`SFSafariViewController`), Copy list, I bought these, wheel create/rename/archive/delete/new URL/take tag, tip colour (`ColorPicker`), manual shade, I wore this + Another, the arrival moment and the haptics map. Flows: `add-bottle`, `bottle-level`, `wishlist`, `wheel-delete`.
4. **The builder**: sheet with detents on compact, inspector on regular, `ArrangementView` on the Duo behind `#available`, every stack operation with optimistic coats/move, the picker with scopes and the P-code suggestion row, templates, Copy from… list, name/note/date, save with the sweep, cancel, remove swatch, resumed drafts, `?hl` from Swatched on. Flow: `builder`.
5. **Scan, tag, NFC, widget**: `DataScannerViewController` wrapper, the Scan screen and its outcomes, learn and learned codes, the Tag page with the native QR, the Core NFC write and check flows with every failure state, the "Wear today" widget with the App Group snapshot, Home's Scan button, the manual checklist as `docs/NATIVE-CHECKLIST.md`. Flows: `scan-typed`, `tag-page`.
6. **Light, Duo polish, accessibility, TestFlight**: `TipLight.metal` + `TipLightModel` with the gates and an Instruments pass, reserved-region handling on the ring page, the four-column Wheels grid, Dynamic Type and VoiceOver audit against 5.10 (fix what the AX pass of the flows shows), Increase Contrast pass, icon layers for Icon Composer, `archive-upload.sh`, `bump-build.sh`, `ExportOptions.plist`, the first archive. Jan runs the upload (or approves the agent's blocked command), then the device checklist.

**Parallelism and boundaries:** S0 → (S1 ∥ app 1) → (S2 ∥ app 2) → app 3 → app 4 → (app 5 ∥ app 6's shader half, if two agents are available; otherwise in order). The web's phase-1 runs 1–3 proceed in parallel throughout: they never touch `app/`, `spec/` or `src/polished/api/`; the only shared files are `tips.py` (S0, coordinated into web run 1) and the `wear` migration (web run 3 and S2 agree on the file name in their briefs). `DESIGN.md` gains a section 17 "API and the native app" in S1 and `docs/NATIVE.md` (this spec) is updated at the end of each app run where the build departs from it.

---

## 9. Flagged: could not verify

- **iPhone Duo simulator poses from the command line** (folded/unfolded, partially folded): no `simctl` subcommand found; Device Hub is documented as the place to "test how your app appears in its various poses" but its CLI surface is unknown. Run 2 investigates.
- **`.sidebarAdaptable` on the Duo inner display**: whether the tab bar becomes a sidebar there is undocumented; the design works either way.
- **Core NFC on iPhone Duo**: assumed present (Apple Pay); the Tag page hides Write when `readingAvailable` is false, so a surprise degrades gracefully.
- **Nikola's iPhone and iOS version**: decides the deployment target (26.0 chosen defensively).
- **Fraunces tabular figures** (`tnum`) in the static instance: checked in run 1, with the frame-based fallback.
- **Apple's AASA CDN through the Cloudflare tunnel**: the `app-site-association.cdn-apple.com/a/v1/polished.janpuc.com` check in the manual list proves it; if Cloudflare's bot rules block the fetch, a WAF skip rule for `/.well-known/apple-app-site-association` is the fix (home-ops, Jan).
- **App Store Connect name "Polished"**: availability unknown until Jan creates the record.
- **`ArrangementView` inside an inspector or sheet**: used only at the screen level (HIG: keep navigation outside it), so this does not block anything.
- **Shader cost with 40 live ring tips**: measured in run 6; the fallback is static light on the ring.

## 10. Sources

Apple newsroom: [Apple unveils iPhone Duo (2026-09-09)](https://www.apple.com/newsroom/2026/09/apple-unveils-iphone-duo/) (5.4" outer, 7.6" inner, same aspect ratio, iOS 27 side controls, Split View on iPhone, continuity across displays, Device Hub support in Xcode); [Developers bring new app experiences to iPhone Duo (2026-10-22)](https://www.apple.com/newsroom/2026/10/developers-bring-incredible-new-app-experiences-to-iphone-duo/) (partially folded poses, "Made for iPhone Duo" badge). Apple developer: [Get ready for iPhone Duo](https://developer.apple.com/iphone-duo/) (Xcode 27.1 is the SDK); HIG [Designing for iPhone Duo](https://developer.apple.com/design/human-interface-guidelines/designing-for-iphone-duo) (compact outer / regular inner, reserved regions, arrangement views, vertical controls, even column counts); [Preparing your app for iPhone Duo](https://developer.apple.com/documentation/technologyoverviews/preparing-your-app-for-iphone-duo) (bars vertical in sheets on the outer display, `toolbarVerticalBehavior`, `presentationPlacement`, `toolbarVerticalEdge`); [ReservedRegion](https://developer.apple.com/documentation/swiftui/reservedregion) and [`reservedRegions(kind:options:layoutDirectionBehavior:)`](https://developer.apple.com/documentation/swiftui/geometryproxy/reservedregions(kind:options:layoutdirectionbehavior:)) (iOS 27.1); [ArrangementView](https://developer.apple.com/documentation/swiftui/arrangementview) (27.1); [ToolbarItemVisibilityPriority](https://developer.apple.com/documentation/swiftui/toolbaritemvisibilitypriority) (27.0); [Device Hub](https://developer.apple.com/documentation/xcode/device-hub). SwiftUI availability (documentation JSON): [`glassEffect(_:in:)`](https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)), [GlassEffectContainer](https://developer.apple.com/documentation/swiftui/glasseffectcontainer), [`glassEffectID`](https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)), [`tabBarMinimizeBehavior`](https://developer.apple.com/documentation/swiftui/view/tabbarminimizebehavior(_:)), [`searchToolbarBehavior`](https://developer.apple.com/documentation/swiftui/view/searchtoolbarbehavior(_:)), [`scrollEdgeEffectStyle`](https://developer.apple.com/documentation/swiftui/view/scrolledgeeffectstyle(_:for:)), [`backgroundExtensionEffect`](https://developer.apple.com/documentation/swiftui/view/backgroundextensioneffect()) (all iOS 26); [`sidebarAdaptable`](https://developer.apple.com/documentation/swiftui/tabviewstyle/sidebaradaptable), [`navigationTransition`](https://developer.apple.com/documentation/swiftui/view/navigationtransition(_:)), [`zoom(sourceID:in:)`](https://developer.apple.com/documentation/swiftui/navigationtransition/zoom(sourceid:in:)), [`matchedTransitionSource`](https://developer.apple.com/documentation/swiftui/view/matchedtransitionsource(id:in:)), [`presentationSizing`](https://developer.apple.com/documentation/swiftui/view/presentationsizing(_:)), [TabRole.search](https://developer.apple.com/documentation/swiftui/tabrole/search) (iOS 18); [`presentationDetents`](https://developer.apple.com/documentation/swiftui/view/presentationdetents(_:)) (16); [`inspector`](https://developer.apple.com/documentation/swiftui/view/inspector(ispresented:content:)), [`sensoryFeedback`](https://developer.apple.com/documentation/swiftui/view/sensoryfeedback(_:trigger:)), [`colorEffect`](https://developer.apple.com/documentation/swiftui/view/coloreffect(_:isenabled:)), [`layerEffect`](https://developer.apple.com/documentation/swiftui/view/layereffect(_:maxsampleoffset:isenabled:)), [`distortionEffect`](https://developer.apple.com/documentation/swiftui/view/distortioneffect(_:maxsampleoffset:isenabled:)), [ShaderLibrary](https://developer.apple.com/documentation/swiftui/shaderlibrary), [SwiftData](https://developer.apple.com/documentation/swiftdata) (17); [NavigationSplitView](https://developer.apple.com/documentation/swiftui/navigationsplitview), [Canvas](https://developer.apple.com/documentation/swiftui/canvas), [`onOpenURL`](https://developer.apple.com/documentation/swiftui/view/onopenurl(perform:)). Frameworks: [NFCNDEFReaderSession](https://developer.apple.com/documentation/corenfc/nfcndefreadersession), [`writeNDEF`](https://developer.apple.com/documentation/corenfc/nfcndeftag/writendef(_:completionhandler:)), [NFC formats entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.nfc.readersession.formats), [Adding support for background tag reading](https://developer.apple.com/documentation/corenfc/adding-support-for-background-tag-reading) (universal link in the first URI record launches the app; Safari otherwise); [DataScannerViewController](https://developer.apple.com/documentation/visionkit/datascannerviewcontroller) and [`isSupported`](https://developer.apple.com/documentation/visionkit/datascannerviewcontroller/issupported); [ASWebAuthenticationSession.Callback](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsession/callback) and [`https(host:path:)`](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsession/callback/https(host:path:)) (needs an associated domain); [Supporting associated domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains); [Supporting universal links in your app](https://developer.apple.com/documentation/xcode/supporting-universal-links-in-your-app); [CMMotionManager](https://developer.apple.com/documentation/coremotion/cmmotionmanager); [WidgetKit](https://developer.apple.com/documentation/widgetkit), [StaticConfiguration](https://developer.apple.com/documentation/widgetkit/staticconfiguration); [App Intents](https://developer.apple.com/documentation/appintents) (cut from v1); [Swift Testing](https://developer.apple.com/documentation/testing). Materials and icon: [Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/liquid-glass), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass) ("a distinct functional layer for controls and navigation elements"), [Creating your app icon using Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer), HIG [App icons](https://developer.apple.com/design/human-interface-guidelines/app-icons) (flattened image allowed). Distribution: [Add internal testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/add-internal-testers) (roles Account Holder, Admin, App Manager, Developer, Marketing; 100 testers), [Invite external testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers), [Upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds) (Xcode, altool, Transporter), [Distributing your app for beta testing and releases](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases). Fonts: [Fraunces](https://github.com/undercasetype/Fraunces) (`fonts/ttf/Fraunces144pt-SemiBold.ttf`, OFL 1.1). Local checks: `xcodebuild -version`, `-showsdks`, `-help`; `xcrun simctl list devicetypes|runtimes`; `xcrun simctl ui`; `xcrun xcresulttool export attachments --help`; `xcrun altool --help`; `brew info xcodegen`.
