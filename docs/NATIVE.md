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

**Minimum OS:** build with the iOS 27.1 SDK, deployment target **iOS 27.0** (changed in run 1, 2026-10-26). Both real phones run iOS 27.1, but on this Mac the iOS 27.1 simulator runtime (24A94425) supports only the `iPhone Duo` device type (`simctl list runtimes -j`), while `iPhone 18 Pro`, `iPhone 18 Pro Max` and `iPad Pro 13-inch (M5)` exist only on the iOS 27.0 runtime (24A434); an app with a 27.1 deployment target cannot be run or tested on either of them. So the target is 27.0, and the 27.1-only Duo APIs (`ReservedRegion`, `ArrangementView`, `toolbarVerticalBehavior`) go behind `if #available(iOS 27.1, *)` (always true on both phones; the Duo simulator runs them). Neither of them owns an iPhone Duo; the Duo layouts are built and checked on the simulator only.

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
    Sources/PolishedModels/         Codable DTOs, enums, labels, GTIN normalisation
    Sources/PolishedAPI/            PolishedAPI protocol, LiveAPI (URLSession), FixtureAPI (previews, widget tests)
    Sources/PolishedStore/          SwiftData cache + Session (Keychain) + write coordinator
    Sources/NailTips/               TipRandom, TipPainter (ops), TipCanvas (drawing), TipShape, TipLight (shader glue)
    Sources/NailTips/Shaders/       TipLight.metal
    Tests/PolishedCoreTests/        Swift Testing: fixtures parity, decoding, normalisation
  PolishedUITests/                  XCUITest flows + Screenshots helper
  Scripts/                          flows.sh, report.py, archive-upload.sh, bump-build.sh
spec/
  tips/cases.json, tips/random.json   renderer conformance (both engines)
  identifiers/gtin.json normalisation vectors
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

Settings: `SWIFT_VERSION 6.0` with strict concurrency, `IPHONEOS_DEPLOYMENT_TARGET 27.0`, `MARKETING_VERSION 1.0.0`, `CURRENT_PROJECT_VERSION` set by `Scripts/bump-build.sh` (`YYYYMMDDHHMM`, UTC), `DEVELOPMENT_TEAM` from `app/Team.xcconfig` (gitignored; template `Team.xcconfig.example`; the team ID is not secret, it appears in the public AASA, but it stays out of the public project file anyway), `CODE_SIGN_STYLE Automatic`, `ITSAppUsesNonExemptEncryption NO` (HTTPS only; skips the export-compliance question on every upload).

`Polished.entitlements`:
```xml
com.apple.developer.nfc.readersession.formats  = [ TAG ]   (App Store Connect rejects NDEF since the iOS 13 SDK: error 90778 "NDEF is disallowed", "TAG is missing"; NFCNDEFReaderSession works with TAG)
com.apple.developer.associated-domains         = [ applinks:polished.janpuc.com, webcredentials:polished.janpuc.com ]
com.apple.security.application-groups          = [ group.com.janpuc.polished ]
```
`Polished-Debug.entitlements` adds `applinks:polished.janpuc.com?mode=developer` and `webcredentials:polished.janpuc.com?mode=developer` so a development build reads the AASA straight from the server (needs Developer Mode → "Associated Domains Development" on the device). Widget: the App Group only. No Keychain sharing: the widget never holds the token.

`Info.plist`: `NFCReaderUsageDescription` "Polished writes the wheel's link to a sticker and checks it.", `NSCameraUsageDescription` "Polished reads the barcode under a bottle.", no `CFBundleURLTypes` (the app registers no URL scheme; see 2.4), `UIAppFonts` [Fraunces144pt-SemiBold.ttf], `UIApplicationSceneManifest` with `UIApplicationSupportsMultipleScenes YES` (Split View and Stage Manager). No `NSMotionUsageDescription`: `CMMotionManager` attitude does not need one.

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
                                   callback: .https(host: "polished.janpuc.com", path: "/auth/app/callback"))
        prefersEphemeralWebBrowserSession = false
server: GET /auth/app/start  → session["app_login"] = {challenge, device, iat} (replaces any pending one);
                                302 /auth/login?next=/auth/app/finish
        (Pocket ID as today: passkey, remember-me, group check)
        GET /auth/app/finish → signed in; mints code (32 random bytes, 60 s TTL, single use, bound to sub + challenge)
                                302 https://polished.janpuc.com/auth/app/callback?code=<code>   (Cache-Control: no-store)
app:    the session claims that https address (it never loads); POST /api/v1/auth/exchange
        {code, verifier, device_name, platform:"ios", app_version}
server: checks TTL, single use, SHA256(verifier) == challenge → inserts api_token, answers {token, token_id, user}
app:    Keychain generic password, kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly, service "com.janpuc.polished", account "api-token"
```

**Why an https callback and not a custom URL scheme.** Any app on a phone can register the scheme `polished`. `/auth/app/start` is a public GET that takes the PKCE challenge from the query, so an attacker who owns such an app could pick their own verifier, get the victim to open the start link, and receive the victim's one-time code at their own scheme handler: code and verifier in one hand, a permanent device token in the exchange. PKCE only protects the code when the callback cannot be intercepted. An https callback can: iOS 17.4+ hands `ASWebAuthenticationSession` the redirect only for an address the app has claimed, and an address is claimed by the domain's own AASA (`webcredentials` lists the app ID, which only the Team that owns the signing identity can ship) together with the `webcredentials:polished.janpuc.com` entitlement. No other app can claim `polished.janpuc.com`. The same file's `applinks` section lists `/w/*` and `/shades/*` only, never `/auth/*`, so a tapped link to the callback opens Safari, not the app.

`GET /auth/app/callback` is a public page for when that address is opened outside the session (a pasted link, a browser, an app that was not signed in): "Open Polished to finish signing in", `noindex`, `Cache-Control: no-store`, no referrer, no script or link. It never reads the `code`, mints nothing and redeems nothing. `/auth/app/start` keeps one pending sign-in per browser session (a second start replaces the first) with a 10-minute maximum age; the code lives 60 seconds and is used up by the first exchange attempt, right or wrong.

`prefersEphemeralWebBrowserSession` is false so Pocket ID's passkey and remember-me are shared with Safari (she signs in once). Tokens never expire by time; they are revoked by **Sign out** (`POST /api/v1/auth/revoke`), from the web's More page ("Devices", a phase-1 addition listed in the contract), or by deleting the row. A 401 from any call clears the Keychain and shows the sign-in screen with the reason. Token storage on the server is `sha256(token)`; the token is shown to nobody after the exchange.

---

## 3. The server contract: `/api/v1`

Built by a separate worker (runs S1 and S2 in section 8). Written as the contract a future standalone engine or another server meets too: JSON only, integers for ids (opaque to clients, no arithmetic), cents for money, ISO dates (`YYYY-MM-DD`) and UTC timestamps (`…Z`), the tip recipe inline (no SVG URLs needed by the app), nothing HTMX- or template-shaped. Source of truth: `spec/api/openapi.yaml`; recorded examples: `spec/api/fixtures/*.json`, exported from the seeded e2e database by `scripts/make_api_fixtures.py`.

**Transport rules.** `Authorization: Bearer <token>` is the only credential the API accepts (cookies are ignored under `/api/v1/`), so the Origin check and CSRF do not apply there; `OriginCheckMiddleware` skips `/api/v1/` when a Bearer header is present. 401 for a missing, unknown or revoked token with `{"error":{"code":"unauthorized"}}`. Every GET answers `ETag` and honours `If-None-Match` (304, empty body); `Cache-Control: private, no-cache`. `X-Polished-Api: 1` on every answer. Versioning: additive changes within v1 (new optional fields, new endpoints); a breaking change is `/api/v2`. Rate etiquette unchanged: the API never contacts the shop except `POST /sync/run` with the existing cooldown.

**Errors.** `{"error": {"code": "<snake_case>", "message": "<her words>", "field": "<optional>", "fields": {"<field>": "<message>"} (optional), "retry_after_s": 61 (cooldown)}}` with the status: 400 `bad_request`, 401 `unauthorized`, 403 `forbidden`, 404 `not_found`, 409 `not_a_draft` | `sync_running`, 422 `validation` (`field` set, `message` as the web shows it: "Use an amount like 15.50."; when several inputs are wrong `fields` lists every one and `field`/`message` are the first), `stack_full`, `empty_stack`, `same_wheel`, 429 `cooldown` (`retry_after_s`, also the `Retry-After` header), 5xx `server_error`.

**Writes (S2).** Bodies are JSON; a PATCH changes only the keys it sends (`null` clears an optional one). Money is `*_cents` (an integer, 0 to 999999). Dates are `YYYY-MM-DD` and may not be after today in the household's time zone (`/me` → `server.timezone`); "today" is also the default for `bought_on` of `bought` and `painted_on` of `save`. Creates answer 201 (`POST /shades`, `/shades/{id}/bottles`, `/wheels`, and `/identifiers` when the code is new, 200 when it was known); deletes of a bottle, wishlist item, identifier and slot answer 204; every other write answers 200 with the changed resource, `POST /sync/run` 202. Repeating is safe where it means the same thing: `PUT /shades/{id}/wishlist` keeps the existing item, `PUT …/tip-colour`, `POST /wear/{id}` (one row per shade per day), `POST …/slots/{pos}/draft` (`resumed: true`), `DELETE …/slots/{pos}` and `PATCH` with the same values. The multi-row writes (`/wishlist/bought`, `/stacks/{id}/save`, bottle create, wheel delete, template, move) run in one transaction: if anything is wrong or fails, nothing changed. Auth: a write without a Bearer token is a 401 and changes nothing, cookie or not.

**P codes (retired 2026-10-28, DESIGN 14 item 88).** Holo Taco's printed P numbers are no longer an identifier. `Bottle` has no `printed_code`; the bottle create answer is `{bottle}` (no `learned`); the lookup outcomes are `match`, `unknown_code`, `invalid_code` and `results` (`kind` is `gtin`, `sku` or null); `GET /stacks/pick` has no `suggestion`; an identifier's `kind` is `gtin` only. Request bodies of bottle create and patch still **accept and ignore** `printed_code`, so a build that sends it gets no 422. The build log in section 8 describes the app before this change.

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
Bottle   {"id": 3, "shade_id": 12, "state": "half", "bought_on": "2026-07-21",
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
| GET | `/.well-known/apple-app-site-association` | public, `application/json`, no redirect: `{"applinks":{"details":[{"appIDs":["<TEAMID>.com.janpuc.polished"],"components":[{"/":"/w/*"},{"/":"/shades/new","exclude":true},{"/":"/shades/*"}]}]},"webcredentials":{"apps":["<TEAMID>.com.janpuc.polished"]}}` (no `/auth/*` in `applinks`); `POLISHED_APPLE_TEAM_ID` setting (empty → 404 and the route is off) |
| GET | `/auth/app/start` | browser, public; see 2.4 |
| GET | `/auth/app/finish` | browser, needs the web session; 302 `https://<host of PUBLIC_URL>/auth/app/callback?code=` (`no-store`) |
| GET | `/auth/app/callback` | browser, public; a harmless page that never reads the code (2.4) |
| POST | `/api/v1/auth/exchange` | public; `{code, verifier, device_name, platform, app_version}` → `{token, token_id, user:{sub,name}}`; 400 `bad_code` |
| POST | `/api/v1/auth/revoke` | revokes the calling token → 204 |
| GET | `/api/v1/auth/devices` | `{items:[{id, device_name, platform, created_at, last_used_at, current}]}` |
| DELETE | `/api/v1/auth/devices/{id}` | 204 (also exposed on the web's More page as "Devices") |
| GET | `/api/v1/me` | `{user:{sub,name,first_name}, server:{version, public_url, store_url, timezone, over_black_available, shade_count}}` |
| GET | `/api/v1/home` | `{greeting_name, date, wear:{shade: ShadeRow, bottle: Bottle, worn_today: bool} \| null, recent:[{bottle: Bottle, shade: ShadeRow}] (6), wheel: Wheel+tiles \| null, counts:{bottles, shades, wished, wished_cents}}`; `wear` is today's pick, the same all day (the shade already worn today, once one was; null when nothing is owned); `?another=1` returns a random other owned shade (weighted away from the last 30 days), never the one shown without it, and does not move today's pick |
| POST | `/api/v1/wear/{shade_id}` | records today (household time zone) → `{worn_on}`; 404 unknown shade; the `wear` table is migration `009_wear.sql`, the rules are `src/polished/wear.py` (the web's Home reuses them) |
| GET | `/api/v1/shades` | same params as `/shades` (`q, finish[], color[], collection, kind, status, owned, sort, page`) → `{items:[ShadeRow], total, page, has_more, fuzzy: bool}` (40 a page) |
| GET | `/api/v1/shades/facets` | `{finish:[], color:[], collection:[], official:[]}` |
| GET | `/api/v1/shades/{id}` | `{shade: ShadeRow, images:[url], tags:{finish,color,collection}, sku, handle, store_url, on_sale, bottles:[Bottle], wishlist:{id, priority, note} \| null, swatched_on:[{wheel_id, slug, name, position, stack_id}], tip_source:"override" \| "sampled" \| "none"}` |
| POST | `/api/v1/shades` | `{title, kind:"polish" \| "topper" \| "base"}` → the detail (201) |
| PUT | `/api/v1/shades/{id}/tip-colour` | `{hex:"#rrggbb"}` or `{hex:null}` → detail; 422 `validation` |
| GET | `/api/v1/bottles` | `?state&archived` → `{groups:[{shade: ShadeRow, bottles:[Bottle]}]}` |
| GET | `/api/v1/bottles/history` | `{years:[{year, count, total_cents, unpriced, months:[{month, label, count, total_cents, unpriced, rows:[{bottle: Bottle, shade: ShadeRow, dated_by_entry}]}]}]}` |
| POST | `/api/v1/shades/{id}/bottles` | `{state, bought_on, price_paid_cents, opened_on, notes}` (all optional, `state` defaults to `full`; a `printed_code` is accepted and ignored, see "P codes" above the table) → `{bottle}` (201); 422 per field |
| PATCH | `/api/v1/bottles/{id}` | any subset of the same fields plus `archived` → Bottle (a `printed_code` is accepted and ignored) |
| DELETE | `/api/v1/bottles/{id}` | 204 |
| GET | `/api/v1/wishlist` | `?max_priority=3` → `{items:[{id, shade: ShadeRow, priority, note, added_on, buyable}], summary:{count, total_cents, buyable_count, buyable_cents}, cart:{url \| null, total_cents, count, skipped, names:[…]}}` |
| PUT | `/api/v1/shades/{id}/wishlist` | `{priority:2}` → the item (existing item kept) |
| PATCH | `/api/v1/wishlist/{item_id}` | `{priority, note}` → the whole wishlist body |
| DELETE | `/api/v1/wishlist/{item_id}` | 204 |
| POST | `/api/v1/wishlist/bought` | `{items:[{id, price_cents \| null}], bought_on}` → `{bottles:[Bottle], wishlist: <body>}`; 404 unknown item, 422 |
| GET | `/api/v1/lookup` | `?q&via=scan \| typed` → `{outcome: match \| unknown_code \| invalid_code \| results, code, kind: gtin \| sku \| null, shade: ShadeRow+images \| null, identifier_id, results:{items, total} \| null}` |
| POST | `/api/v1/identifiers` | `{kind: "gtin", value, shade_id}` (any other `kind` is a 422) → `{identifier:{id, kind, value, shade_id}, created: bool, shade: ShadeRow}`; 201 when new, 200 when the code was known (it keeps its shade, `shade` is that one) |
| GET | `/api/v1/identifiers` | `{items:[{id, kind, value, shade: ShadeRow, use_count, created_at, last_used_at}]}` |
| DELETE | `/api/v1/identifiers/{id}` | 204 |
| GET | `/api/v1/wheels` | `?archived` → `{items:[Wheel+{tiles:[Tile]}]}` (tiles included: the list draws mini rings) |
| POST | `/api/v1/wheels` | `{name, slot_count}` → Wheel (201); 422 |
| GET | `/api/v1/wheels/{id}` and `/api/v1/w/{slug}` | `Wheel + {tiles:[Tile], filled_count, others:[{id, name, slug}]}`; unknown → 404 (after auth, as the web) |
| PATCH | `/api/v1/wheels/{id}` | `{name}` or `{archived}` → Wheel |
| DELETE | `/api/v1/wheels/{id}` | → `{deleted_swatches: 3}`; no confirmation parameter, the app asks first |
| POST | `/api/v1/wheels/{id}/slug/regenerate` | → Wheel (new slug) |
| POST | `/api/v1/wheels/{id}/slug/take` | `{from_wheel_id}` → Wheel; 422 `same_wheel` |
| POST | `/api/v1/wheels/{id}/slots/{pos}/draft` | → Sheet (below), `resumed: bool` |
| DELETE | `/api/v1/wheels/{id}/slots/{pos}` | clear the swatch → 204 |
| GET | `/api/v1/stacks/{id}` | Sheet `{stack_id, wheel:{id, slug, name}, position, name, note, painted_on, layers:[Layer], summary, full, tip: Tip[] (the composite recipe = layers' tips in order)}` ; 409 `not_a_draft` |
| POST | `/api/v1/stacks/{id}/layers` | `{shade_id}` → Sheet; 422 `stack_full` |
| PATCH | `/api/v1/stacks/{id}/layers/{layer_id}` | `{coats_delta: ±1}` or `{move: "up" \| "down"}` (exactly one) → Sheet; coats stay 1 to 5, `up` is towards the base |
| DELETE | `/api/v1/stacks/{id}/layers/{layer_id}` | → Sheet |
| POST | `/api/v1/stacks/{id}/template` | `{kind:"over_black"}` → Sheet + `{result: added \| already \| unavailable}` (200; 422 `stack_full`); `{kind:"copy", source_stack_id}` → Sheet + `result: copied` (404 when the source is not a saved stack); `{kind:"last"}` → Sheet + `result: copied \| nothing_saved` |
| GET | `/api/v1/stacks/copy-sources` | `?q` → `{items:[{stack_id, wheel_name, wheel_slug, position, name, painted_on, summary, layers}]}` |
| GET | `/api/v1/stacks/pick` | `?q&scope=owned \| toppers \| all` → `{items:[ShadeRow], total}` (a barcode the household taught the app comes back as the one item; digits that are not a barcode are a name search) |
| POST | `/api/v1/stacks/{id}/save` | `{name, note, painted_on}` → `{wheel_id, position, tile: Tile}`; 422 `empty_stack`, or `validation` on `painted_on` (not a date, or in the future) |
| POST | `/api/v1/stacks/{id}/cancel` | → `{wheel_id, position, tile: Tile}` |
| GET | `/api/v1/sync` | `{running: bool, last:{started_at, finished_at, status, trigger, counts…}, runs:[…10], cooldown_until}` |
| POST | `/api/v1/sync/run` | 202 `{run_id}` (the run goes on in the background; poll `GET /sync`); 409 `sync_running`; 429 `cooldown` with `retry_after_s` |
| POST | `/__test/reset` | **only** when `POLISHED_AUTH_MODE=none` and `POLISHED_TEST_RESET_FROM=<template.db>`; copies the template over the live DB; loopback only. For the UI-test harness |

Server-side files: new package `src/polished/api/` (`__init__.py` router, `auth.py` tokens, `schemas.py` pydantic models, `shades.py`, `bottles.py`, `wishlist.py`, `wheels.py`, `stacks.py`, `lookup.py`, `home.py`, `sync.py`), migrations `008_api_tokens.sql` (`api_token(id, user_sub, user_name, device_name, platform, token_hash unique, created_at, last_used_at, revoked_at)`, `app_login_code(code_hash, user_sub, user_name, challenge, device_name, expires_at, used_at)`) and `009_wear.sql` (`wear(id, shade_id, worn_on, created_at)`, unique `(shade_id, worn_on)`), `auth.py` gains the three browser routes (start, finish, callback) and a Bearer branch in the gate (`/api/v1/` paths: Bearer or 401 JSON, never a redirect), `security.py` the Origin bypass (and `no-store` kept on HTML), `server.py` one `include_router`. Domain modules are reused unchanged; the API serialises their dicts. Tests `tests/test_api_*.py` against the fixtures, plus a test that every fixture in `spec/api/fixtures/` validates against `openapi.yaml`.

---

## 4. The tip renderer port

### 4.1 One recipe, one list of paint operations, two engines

`tips.py` is split in two: `ops(layers) -> list[dict]` (the paint plan) and `svg(ops)` (today's markup). `render()` is `svg(ops(layers))` and its tests stay; `tests/fixtures/tip_svg_sha1.json` pins the SVG of every fixture case (the split was proved byte-identical to the old code before the generator changed). `ops()` returns full-precision numbers; only the fixture file is rounded. The Swift `TipPainter.ops(for layers: [TipShade]) -> [TipOp]` must produce an equal list. Fixtures: `spec/tips/cases.json` (`{"source":"tips.py@<sha>","cases":[{"name","layers":[TipShade…],"ops":[…]}]}`, 46 cases: every finish alone, every finish as a topper, jelly over black, flakie over nothing, thermal with and without hex2, matte top, chrome + flakie, an 8-layer stack, clear base alone, empty list, and a few more) generated by `scripts/make_tip_fixtures.py`. A `layers` entry is `{id, hex, hex2, finishes (sorted), topper, clear, coats, colours (sorted, or null when the row carried no colour tags)}`. Numbers in the IR are rounded to 3 decimals and compared with tolerance 0.001; colours are lowercase `#rrggbb`.

Op kinds (the SVG elements tips.py already emits, no more):
```jsonc
{"op":"rect","fill":{"kind":"solid","color":"#c72bb9"},"opacity":1}
{"op":"rect","fill":{"kind":"linear","x1":0,"y1":0.15,"x2":1,"y2":0.85,"stops":[[0,"#ff5fa2",0.11],…]},"opacity":1}
{"op":"rect","fill":{"kind":"radial","cx":0.5,"cy":0.42,"r":0.78,"stops":[[0.55,"#000000",0],[1,"#000000",0.18]]},"opacity":1}
{"op":"dots","color":"#f2a9d6","opacity":0.5,"circles":[[cx,cy,r],…]}
{"op":"star","cx":40.1,"cy":77.3,"size":3.2,"color":"#ffffff","opacity":0.9}
{"op":"polygon","points":[[x,y],…],"color":"#71ad44","opacity":0.63,"stroke":"#ffffff","stroke_opacity":0.35,"stroke_width":0.4}
{"op":"path","d":"M-8 150Q51 52 112 96L112 128Q51 84-8 176Z","color":"#…","opacity":0.75,"blur":3.5}
{"op":"path","d":"M25 30C26 20 37 20 39 30L36 98C35 106 29 105 28 97Z","fill":{"kind":"linear","x1":0,"y1":0,"x2":0,"y2":1,"stops":[[0,"#ffffff",0.5],[1,"#ffffff",0.03]]},"opacity":1}
{"op":"ellipse","cx":66,"cy":30,"rx":6,"ry":15,"rotate":14,"color":"#ffffff","opacity":0.1}
```
The gloss highlight is the one `path` with a gradient `fill` instead of a `color`; its coordinates are fractions of that path's bounding box (SwiftUI: `.linearGradient(…, startPoint:, endPoint:)` fills the path's bounds). A magnetic layer emits two `path` ops (blur 3.5 each; the SVG shares one filter between them). Opacity is always present; in the markup a `rect` draws it only below 1. Canvas 102×168, `slice` fit (SwiftUI: `.aspectRatio(102/168, contentMode: .fill)` inside the clip). The two v3 run-1 tweaks (dome edge `.24 → .18`, highlight ellipse `(70,34) → (66,30)`) were already in `tips.py`; the fixture header records the commit (`tips.py@<short sha>` of HEAD when it was generated; the regeneration test ignores that field).

### 4.2 The random generator: SplitMix64 in both engines (a change to `tips.py`)

CPython's `random.Random` is MT19937 plus CPython-specific `randbelow` rejection sampling; porting it bit-for-bit is possible but a trap for an agent. The spec therefore defines the generator, and `tips.py` adopts it in the same commit as the split (the only visible change: dust, glitter and flake positions move once; `tips.DRAWING_VERSION` went 2 → 3, which is mixed into `revision()` and so into the image URL, so cached SVGs refresh). `revision()` also hashes sorted tuples now: it used the repr of frozensets, which varies with `PYTHONHASHSEED`, so it changed on every server restart:

```
TipRandom(seed: UInt64)           state = seed (the shade id)
next() -> UInt64: state &+= 0x9E3779B97F4A7C15; z = state
                  z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9; z = (z ^ (z >> 27)) &* 0x94D049BB133111EB; return z ^ (z >> 31)
random() -> Double  = Double(next() >> 11) * 0x1.0p-53
uniform(a, b)       = a + (b - a) * random()
below(n)            = Int(random() * Double(n))          (n < 2^20)
choice(seq)         = seq[below(seq.count)];  randint(a, b) = a + below(b - a + 1);  randrange(n) = below(n)
```
Python: `class TipRandom` (20 lines, masks with `& (2**64 - 1)`), used as `rng = TipRandom(shade.id)`; call order in `_paint` unchanged. `spec/tips/random.json` holds, for seeds 0, 1, 7, 259, 2**32+5, `{seed, random: [first ten random() values], below_1000: [the next ten below(1000) values]}` from one generator per seed (full precision doubles; seed 0's first `next()` is `0xE220A8397B1DCDAF`). If Jan prefers the web tips untouched, the fallback is an exact MT19937 port (init_by_array seeding, 53-bit `random()` from two draws, `getrandbits`-based `_randbelow`); the fixture test is the same either way.

### 4.3 Drawing in Swift

- `TipShape: Shape`: the CSS radius `50% 50% 38% 38% / 62% 62% 30% 30%`, i.e. top corners with radii (0.5 w, 0.62 h), bottom corners (0.38 w, 0.30 h), each corner a quarter ellipse (four cubic arcs, kappa 0.5523). Used for clip, the die-cut stroke and the contact shadow.
- `TipCanvas: View` = `Canvas { ctx, size in … }` drawing the ops scaled to `size` (102→w): `rect` → `ctx.fill(Path(CGRect), with: .color / .linearGradient(Gradient(stops), startPoint:, endPoint:) / .radialGradient(…, center:, startRadius: 0, endRadius: r·w))`, `dots` → one `Path` of ellipses per group, `star`/`polygon`/`path` → `Path` (an SVG path parser for the two fixed magnetic paths is 40 lines; or hard-code them as `Path` builders keyed by the op's `d`, since tips.py has exactly two), `blur` → `ctx.drawLayer { $0.addFilter(.blur(radius:)) … }`, `ellipse` with rotation via `ctx.rotate`. Rendered once per (recipe, size) into an image cache (`ImageRenderer` at 3×, LRU 300 entries; the lit chrome around the image is drawn live, so the colour scheme is not in the key) so lists scroll at 120 Hz; the hero, rack and ring tips draw live (`TipView(painting: .direct)`). Built in run 1, with two departures the parity montage forced: (1) SVG interpolates a gradient's colour and opacity separately, SwiftUI interpolates premultiplied colours, which makes a fade from a colour to a darker one (the jelly's depth gradient) dark too early; `TipCanvas.gradient` therefore inserts intermediate stops worked out in straight alpha. (2) Gradients that SVG measures in `objectBoundingBox` (the radial dome, every diagonal) are drawn in a context mapped to the unit square of the tip or of the path's tight bounds (`SVGPath.tightBounds`, not `Path.boundingRect`, which includes control points), so they stretch like the SVG's. The two magnetic paths are parsed from their `d` (`SVGPath`, about 90 lines with the bounds).
- `TipView(recipe, size: .s/.m/.l/.xl/.ring, light: .static/.live)` reproduces v3 §2.4 around the canvas: contact shadow (ellipse 76% wide, 16% tall at the foot, `ShadowInk` 26% light / black 55% dark, blur 4), die-cut edge (`Surface` 1.5 pt + 1 pt `ShadowInk` 18% + soft 8/18 drop), inside: `Mat` 1 pt inset stroke, `Rim` 1 pt top-left highlight, 2 pt bottom-right occlusion, then the light overlay in `.softLight` (see the note after this list): radial pool at (50% + lx·40%, 50% + ly·40%) 60×40%, white 50%, and the 115° band (transparent 38%, white 35% at 48%, transparent 58%). Sizes (pt): s 28×46, m 40×66 (44×72 regular), l 72×118 (88×144 regular), xl 96×158 (120×197 regular), ring slot 38×62 (44×72 regular).

Run 1 note on the light: SwiftUI's `.softLight` is Core Graphics' formula, which lifts red and blue more and green less than CSS (W3C) soft-light, so white 50% and 35% made the pool and band pink. The lit face therefore draws each as a smaller soft-light part (pool 25%, band 12%; the mat, rim and occlusion stay in soft-light) plus a plain white lift (pool 8%, band 9%); on the parity montage (`app/Scripts/parity.sh`, twelve recipes, light and dark) the mean absolute difference from the web's tip is 1.0 to 1.3 of 255 per tip. The exact fix is a shader (run 6's `TipLight.metal` can take it over).

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
| Scan | full-screen cover: VisionKit view, framing guide, torch, Close, a text field "Type the digits or a name" under it, result card, Learned codes link | centred 480 pt viewfinder, result beside from 1000 pt |
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
│ ▐▓▓▓▌  Half left                                     │
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
│  ♡ Wishlist   │ Swatches                                                  │ [ ⌕ Search shades                   ] [▣] │
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
[ ⌕ Search shades                                   ] [▣]
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
[ Type the digits or a name                     ]
┌ result ──────────────────────────────────────┐
│ [photo 72×96] ▐▓▓▌ Spirit Fingers            │
│               Glitter, holographic   $15.50  │
│ [ Add bottle ]         This isn't it         │
└──────────────────────────────────────────────┘
Learned codes ›
```
Outcomes map to the web's: `match` (card, Add bottle, This isn't it), `unknown_code` ("New barcode. Which shade is this?" + picker; choosing learns then opens Add bottle), `invalid_code` ("Couldn't read that reliably. Try again."), `results`.

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

- **Fraunces144pt-SemiBold.ttf** (static instance, SIL OFL 1.1, from the Fraunces repo `fonts/ttf/`; it bakes in `opsz 144`, `wght 600`, SOFT 0, WONK 0, exactly the v3 cut). Four roles only: Greeting (`Font.custom("Fraunces144pt-SemiBold", size: 34, relativeTo: .largeTitle)`, 40 on regular), Shade title (28, `.title`), Wheel name (22 cards, 34 page), Hub and Collection numbers (56 on the ring, 28 on Home; tabular via `UIFontDescriptor` feature `kNumberSpacingType / kMonospacedNumbersSelector`; run 1 checked: the static instance has no `tnum` (GSUB features are `aalt`, `case`, `liga`, `locl`, `ss01`; the 0 is 1226 units wide, the 1 is 744), so `DisplayNumber` sets each digit in a cell as wide as the 0). Never below 22 pt, never in rows, buttons, labels, chips or tabs. Dynamic Type: the roles scale with their text style but are capped at ×1.35 (`dynamicTypeSize(...DynamicTypeSize.xxxLarge)` on those views only) so the greeting holds one line.
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

- VoiceOver: tips are decorative in rows (`accessibilityHidden`) and the row carries one label: "Spirit Fingers, glitter, holographic, wished, owned twice, $15.50". Bottle rows: "Spirit Fingers, half left, bought 21 July 2026, $15.50". Ring slots are buttons: "Slot 12, One-Coat Black + Flakie Holo Taco, painted 20 October" / "Slot 3, empty" / "…, draft in progress". The hero: "Wear today: Acid Drip, holographic, metallic, shimmer, half left". The wheel's hub is one element: "14 of 20 slots filled". Rotor actions on rows: wishlist, level, remove.
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
- **Normalisation**: `spec/identifiers/gtin.json` vector (the GTIN check digit, the 14-digit rule).
- **Marks**: `AttributedString` highlighting from `marks` on titles with `™`, accents and combining marks (`spec/api/fixtures/shades-search-*.json` carry marks from the server).
- **Deep links**: `/w/k3m9xq` → wheel route; `/w/K3M9XQ`, `/w/../x`, `/shades/abc` → rejected.
- **Light model**: roll 0 / pitch 0 → default light; ±40° clamps to ±20°; Reduce Motion freezes.

### 6.2 XCUITest flows mirroring `tests/e2e/run_flows.py`

The app under test talks to **the real server, locally**: `app/Scripts/flows.sh` seeds a template DB with `uv run python tests/e2e/flows/seed.py`, starts `polished serve` with `POLISHED_AUTH_MODE=none POLISHED_PUBLIC_URL=http://127.0.0.1:8080 POLISHED_TEST_RESET_FROM=<template>`, and launches the app with `-server http://127.0.0.1:8080 -token dev -uitest 1` (DEBUG builds only honour these). Each test's `setUp` posts `/__test/reset`, so flows never see each other's data, exactly like the web harness. No URLProtocol stubs: the contract is exercised end to end. `FixtureAPI` exists only for previews and widget tests.

Flows (one XCTestCase each, steps named like the web's, a screenshot attachment per step with `lifetime = .keepAlways`):
`search` (exact title first, "magentic taco" fuzzy with marks, "onecoat", accents, no match → Add it by hand), `add-bottle` (shade → Add bottle sheet → level, date presets, price → arrival), `bottle-level` (half → low → empty → archived under Past bottles), `wishlist` (heart, priority, checkout link present, I bought these → bottles, item gone, History shows it), `builder` (wheel → slot 12 → Over black → search "flak" → add → coats + → Save swatch → tile filled, Swatches row), `wheel-delete` (Delete → confirmation sheet → gone, status line), `history`, `tabs` (every tab and Settings once), `scan-typed` (the Scan screen's field: `259` → suggestion; `810170284120` → unknown code → learn → Add bottle), `tag-page` (QR shown, address, Write hidden on simulator with the lede, Check hidden), `deep-link` (`xcrun simctl openurl booted https://polished.janpuc.com/w/<slug>` → the wheel; needs the Debug `?mode=developer` association, else the test launches the app with `-open <url>` and exercises the router), `signin` (the sign-in screen renders; the session itself is device-only).

Destinations and schemes: `platform=iOS Simulator,name=iPhone 18 Pro,OS=27.0`, `name=iPad Pro 13-inch (M5),OS=27.0` and `name=iPhone Duo,OS=27.1` (the 27.1 runtime has only the Duo, see section 1); light and dark (`xcrun simctl ui <udid> appearance dark` before the run), plus one extra pass on the iPhone at `-UIPreferredContentSizeCategoryName UICTContentSizeCategoryAccessibilityL` and one with `increase_contrast enabled`. **iPhone Duo folded versus unfolded (checked in run 2):** `simctl` has no fold or pose subcommand (`xcrun simctl help` in Xcode 27.1; the device type's `profile.plist` lists none either) and the Duo runs headless under `xcodebuild` with one 1398 x 2034 display. Device Hub's page "Interacting with your app in Device Hub" does document poses: buttons under the bezel for Closed, Partially Open and Open, and Option-drag on a slider for any angle. That is GUI only; nothing scriptable was found. So the flows run in the simulator's default pose (the compact, outer-display size) and the unfolded layout is checked by hand in Device Hub or on the device. The iPad run covers the regular-width layout in the meantime.

Report: `xcodebuild test … -resultBundlePath out.xcresult`, then `xcrun xcresulttool export attachments --path out.xcresult --output-path shots/` (`manifest.json` maps files to tests), and `app/Scripts/report.py` writes `~/.cache/polished/native-flows/<timestamp>/index.html` in the style of `tests/e2e/flows/report.py` (grid: flow × device × scheme, step names, pass/fail, the screenshots). Exit 1 on any failure. The runtime must be installed first: `xcodebuild -downloadPlatform iOS`.

### 6.3 Device-only, with the manual checklist for Jan

Cannot run on a simulator: Core NFC (write, check, background tag read), the camera (live scan), universal links from a real tap (Safari, Messages, NFC, the Camera app's QR), haptics, Core Motion tilt light, Low Power Mode behaviour, the Duo's real poses and Split View, TestFlight install, Pocket ID passkey sign-in.

Checklist (iPhone, after the first TestFlight build; run 5 wrote the Scan and Tag steps). Core NFC and the camera need the signed build on a real phone with the Associated Domains and NFC capabilities enabled by the first `-allowProvisioningUpdates` archive (section 7). A Debug build has `-nfc` and `-server` launch arguments; a TestFlight build has none of them.

1. **Install and sign in.** Install from TestFlight, open Polished, sign in with the passkey, land on Home with the greeting.
2. **Light.** Shades, Spirit Fingers: the zoom, the tilt light moves with the phone, Reduce Motion stops it.
3. **Scan the Spirit Fingers bottle** (barcode `810170284120`, stored as `0810170284120`). Home, tap the barcode button beside the search field (or Bottles, the barcode button in the top bar).
   - The first time, allow the camera. A grey box says "Point at the barcode under the bottle" with a white frame and the torch at the top left (turn it on in a dim room).
   - Hold the bottle 15 to 25 cm away with the barcode inside the frame. The code is highlighted, the frame turns green and the phone taps once (the rigid haptic).
   - First scan on a fresh server: a card "New barcode 0810170284120. Which shade is it?" with a search field. Type `spirit`, tap **Spirit Fingers**: "Saved. 0810170284120 is now Spirit Fingers." with the bottle photo and the painted tip. (On Jan's server the seed learned it before; if the card says "Barcode 0810170284120 is Spirit Fingers" go on to the next step, or tap **This isn't it** and **Forget it** to see the unknown card.)
   - Tap **Add bottle**: level, date, More details has Price paid, Opened on and Notes. **Add bottle** in the top right closes the scan screen, the arrival moment plays on the tip and the success haptic lands.
   - Scan the same bottle again: the card says "Barcode 0810170284120 is" Spirit Fingers directly. Typing `259` is a name search, not a code.
   - Settings (the mark on Home), **Learned codes**: the barcode is listed with its shade and use count; swipe left and tap **Forget** removes it.
   - Deny the camera in iOS Settings, reopen the scan screen: "Camera access is off for Polished. Allow it in Settings, or type the digits below." with **Allow camera access in Settings** (opens the app's page in the Settings app); the typed field still works.
   - In the layer builder (a wheel slot): the barcode button beside the search field scans a bottle and **Add layer** paints it on top.
4. **Write the sticker** (an NTAG213 or larger NFC sticker; one that has never been locked). Wheels, Holos, scroll to the foot, **Tag and QR**.
   - The QR code, the address `https://polished.janpuc.com/w/<slug>`, **Copy** and the share button; under the buttons "Not written yet".
   - Tap **Write to sticker**: iOS shows its NFC sheet "Hold the top of your iPhone to the sticker". Touch the top edge of the phone to the sticker and hold still for a second or two.
   - Success: the sheet says "Written. Tap it with your iPhone to open Holos.", the phone taps, the page shows "Written <date, time>" and a green line with the same words.
   - Failures to see once, with the right stickers: a locked sticker says "This sticker is locked. Use another one."; a very small one "This sticker is too small. Use an NTAG213 or larger."; pulling the sticker away early "The sticker moved. Hold it still and try again."; waiting a minute "Nothing was written. Try again and hold still." The button turns into **Try again**.
5. **Check the sticker.** Tap **Check the sticker** and touch the sticker: "This sticker opens Holos." A sticker written for another wheel says "This sticker opens Toppers, not this wheel."; a blank one "This sticker is empty."; a sticker with some other link "This isn't one of ours. It opens <address>."
6. **Tap the sticker with the app closed** (swipe Polished away first): iOS shows a notification "Open polished.janpuc.com", tap it, the app opens on Holos (the wheel page, not Home). Repeat with the app in the background and with Polished open on another tab: each lands on the wheel. (If a banner never appears, check Settings, NFC, and that Associated Domains Development is on for a Debug build; a TestFlight build reads Apple's CDN copy of the file, step 14.)
7. **Delete the app and tap the sticker again:** Safari opens the wheel on polished.janpuc.com (it asks you to sign in). Reinstall from TestFlight.
8. **QR code:** open the Tag page on Nikola's phone, scan its QR with the Camera app: the banner "Open in Polished" opens the app on the wheel.
9. **Links in Messages:** send yourself `https://polished.janpuc.com/w/<slug>` (the app opens the wheel) and `https://polished.janpuc.com/shades/<id>` (the shade); `https://polished.janpuc.com/wishlist` opens Safari.
10. **Move the tag:** on the Tag page, **New tag URL** asks "Make a new tag URL? The old sticker will stop working." Confirm; the QR and address change and "Written" resets to "Not written yet". Tap the old sticker: Safari shows a not-found page. **Write to sticker** with the new address and check it. **Take the tag of…** another wheel swaps the two tags: the sticker you already have opens the other wheel.
11. **Mac Safari:** the same links open the web, not an app.
12. **Devices:** Settings, Devices lists both phones; Sign out revokes; the web's Devices page shows the revocation.
13. **iPhone Duo:** Home closed, open it mid-scroll (state kept), rotate, Split View with Safari beside Polished, the wheel page partially folded (ring upright, builder flat); the builder beside the ring on the open display hides the wheel list column while it is up.
14. **Low Power Mode:** the light freezes. **Widget** (run 6): add Wear today, tap it, the shade opens. `curl https://app-site-association.cdn-apple.com/a/v1/polished.janpuc.com` returns the AASA (Apple's CDN fetched it through the Cloudflare tunnel).

---

## 7. Distribution

- **TestFlight, internal testing.** Internal testers must be App Store Connect users; the roles allowed are Account Holder, Admin, App Manager, Developer or Marketing (Apple's "Add internal testers" help, read today). Invite Nikola as a user with the **Marketing** role, restricted to this one app: the least privileged role that can test, no access to builds, certificates or finances. Internal builds skip Beta App Review, reach testers within minutes of processing and expire after 90 days; 100 testers max. External testing by email would need the one-time Beta App Review for the first build and gains nothing here, so no.
- **App record** (created by Jan on 2026-10-26): name **"Polished: Swatch Book"** ("Polished" was taken; the name on the Home Screen is `CFBundleDisplayName` "Polished" regardless), primary language English, bundle ID `com.janpuc.polished`, SKU `polished-ios`. Do **not** tick "Make available on Mac" (section 1).
- **Signing:** automatic; the first `xcodebuild -allowProvisioningUpdates` with the API key registers the App ID with NFC Tag Reading, Associated Domains and App Groups and creates the profiles. If a capability refuses to auto-enable, Jan adds it under Certificates, Identifiers & Profiles → Identifiers → `com.janpuc.polished`.
- **App Store Connect API key** (Jan): Users and Access → Integrations → Team Keys → generate, role **App Manager** (upload needs Developer or higher; App Manager also lets a later script manage groups), download `AuthKey_<KEYID>.p8` once, store the file, key ID and issuer ID in 1Password. Done 2026-10-26: item "App Store Connect API key, polished" in the vault **Kubernetes**, category API credential, fields `KEY_ID` and `ISSUER_ID`, the key attached as the file `AuthKey_<KEY_ID>.p8` (read with `op read "op://Kubernetes/App Store Connect API key, polished/KEY_ID"` and the file by its name). The script reads them with `op read` into `~/.appstoreconnect/private_keys/` (altool's and xcodebuild's expected location) for the duration of the upload.
- **Archive, export, upload from the CLI** (built in run 6a; `app/Scripts/archive.sh`, `bump-build.sh`, `upload.sh`, `lib/asc.sh`, `app/ExportOptions.plist`). Everything lands in `app/build/` (gitignored).
  1. Credentials, from the environment, never from the repository: `ASC_KEY_ID`, `ASC_ISSUER_ID` and `ASC_KEY_PATH` (default `~/.appstoreconnect/private_keys/AuthKey_${ASC_KEY_ID}.p8`). When the two IDs are unset the scripts read `~/.cache/polished/asc.env` (`ASC_KEY_ID=…`, `ASC_ISSUER_ID=…`) if it exists, and fail with a sentence naming what is missing.
  2. `app/Scripts/archive.sh`: `xcodegen generate` → `Scripts/bump-build.sh` → `xcodebuild -project Polished.xcodeproj -scheme Polished -configuration Release -destination 'generic/platform=iOS' -archivePath build/Polished.xcarchive -derivedDataPath build/DerivedData archive -allowProvisioningUpdates -authenticationKeyPath … -authenticationKeyID … -authenticationKeyIssuerID …` → `xcodebuild -exportArchive -archivePath build/Polished.xcarchive -exportOptionsPlist ExportOptions.plist -exportPath build/export -allowProvisioningUpdates <the same three flags>`. `ExportOptions.plist` is `{method: app-store-connect, destination: export, signingStyle: automatic, teamID: RW5T9P5A59, uploadSymbols: true, manageAppVersionAndBuildNumber: false}`: the export **does not upload**; it leaves `build/export/Polished.ipa` and deletes the `.xcarchive`. `archive.sh --unsigned` stops after an archive built with `CODE_SIGNING_ALLOWED=NO` (no key, nothing for a device) and is the quick proof that the Release configuration compiles and links.
  3. `app/Scripts/upload.sh` (orchestrator or Jan, once `build/export/Polished.ipa` exists): `xcrun altool --upload-package build/export/Polished.ipa --wait --api-key "$ASC_KEY_ID" --api-issuer "$ASC_ISSUER_ID" --p8-file-path "$ASC_KEY_PATH"`. Checked against `xcrun altool --help` (Xcode 27.1, altool 27.0.5): the options are now `--api-key` and `--api-issuer` (the old `--apiKey` spelling is only on the `--generate-jwt` line), `--upload-package` is the documented upload (`--upload-app -f` is still listed), `--wait` blocks until App Store Connect has processed the build and no `-t` is needed. `xcrun altool --build-status --apple-id <id> --bundle-version <build>` checks it later.
  4. Run it as one block: `cd app && Scripts/archive.sh && Scripts/upload.sh`. Nothing here runs by itself; an agent runs `archive.sh` and stops before `upload.sh`.
  - **Verified in run 6a:** the unsigned Release archive builds; its `Info.plist` has `CFBundleShortVersionString` 1.0.0, `CFBundleVersion` the UTC minute, `CFBundleDisplayName` Polished, `ITSAppUsesNonExemptEncryption` false, the 1024 px icon compiled to `Assets.car` plus `AppIcon60x60@2x.png` and `AppIcon76x76@2x~ipad.png`, `PrivacyInfo.xcprivacy` in the bundle, the widget extension with the same two version strings, and no `TipCases.json`.
  - **The signed archive:** the API key was found valid (the App Store Connect API answers it: apps, bundle IDs, certificates, profiles, users) and the team of `com.janpuc.polished` is `RW5T9P5A59`, but `xcodebuild archive -allowProvisioningUpdates -authenticationKey…` with it answered, for both targets, `error: Authentication failed: Make sure a bearer token was provided, it is properly configured and signed, and it has not expired.` followed by `No profiles for 'com.janpuc.polished' were found: Xcode couldn't find any iOS App Development provisioning profiles matching 'com.janpuc.polished'.` (and the same for `com.janpuc.polished.widgets`, whose App ID does not exist yet). The key is probably short of the role Xcode needs to create App IDs, capabilities and profiles (App Manager is what section 7 chose; Admin is the role that can manage Certificates, Identifiers & Profiles); if so, generate the key with the Admin role (or add the App IDs and capabilities by hand, below) and run `archive.sh` again. Not verified further.
- **Release configuration** (checked in run 6a): `Polished.entitlements` (applinks and webcredentials for `polished.janpuc.com` with no `?mode=developer`, NFC `TAG` (not `NDEF`, which App Store Connect rejects with error 90778), the App Group), never the `-Debug` file; the DEBUG-only code (the tip gallery and parity screens, `-screen`, `-server`, `-token`, `-uitest`, `-open`, `-signedout`, `-nfc`, `-tab`, the fake sticker, the `TipCases.json` copy) is compiled out by `#if DEBUG`, so the server is `https://polished.janpuc.com` and there is no development token; `Info.plist` carries `CFBundleShortVersionString` `$(MARKETING_VERSION)` and `CFBundleVersion` `$(CURRENT_PROJECT_VERSION)` in both targets (the widget's must equal the app's); `Polished/PrivacyInfo.xcprivacy` declares no tracking, no collected data types, and the one required-reason API the app uses, `UserDefaults` with reason `CA92.1` (the Tag page's "Written" dates; no file timestamp, disk space, boot time or keyboard API is called).
- **Capabilities if automatic signing cannot add them:** Certificates, Identifiers & Profiles → Identifiers → `com.janpuc.polished` needs **App Groups** (`group.com.janpuc.polished`), **Associated Domains** and **NFC Tag Reading**; the widget's App ID `com.janpuc.polished.widgets` needs **App Groups** with the same group. The first signed `-allowProvisioningUpdates` archive is meant to do this; if it reports a capability it cannot enable, add it here and archive again.
- **Build numbering:** `MARKETING_VERSION` 1.0.0 (bumped by hand per milestone, `project.yml`), `CURRENT_PROJECT_VERSION` = `date -u +%Y%m%d%H%M` at archive time (monotonic, unique per minute, 12 digits). `bump-build.sh` writes it to `app/Build.xcconfig` (gitignored), which `Config.xcconfig` includes after its default of 1, so `project.yml` never changes and Debug builds keep 1. Both numbers are stamped into the Settings version row ("1.0.0 (202610261842)"). App Store Connect refuses a build number it has seen, so a failed upload is archived again with a new minute.
- **After the upload (TestFlight):** processing takes 5 to 20 minutes (`upload.sh --wait` returns when it is done; the build shows "Processing" and then "Ready to Submit" under TestFlight → iOS Builds). The first build asks for **Export Compliance**: the app sets `ITSAppUsesNonExemptEncryption` to NO, so the question is skipped; if it appears anyway, answer that the app uses no encryption beyond what iOS provides. Then, once: TestFlight → Internal Testing → **+** → group "Household" → tick **Enable automatic distribution** → add Jan and Nikola (App Store Connect users; she accepts the invitation email first) → the group's builds list shows the build; every later build reaches both phones without another click. On each phone: TestFlight app → Polished → Install (or Update). Internal builds need no Beta App Review and expire after 90 days. Then the checklist of 6.3.
- **What Jan clicks himself:** accept the current Program License Agreement; create the app record; generate the API key into 1Password; invite Nikola (Marketing, one app) and confirm she accepts the email and installs TestFlight; create the internal group "Household" with automatic distribution and add both; enable Developer Mode on both phones (and "Associated Domains Development" on his for Debug builds); install the first build; run the checklist of 6.3; later, Icon Composer (5.11). Everything else is scripted.

---

## 8. Staged implementation plan

(The built-log entries below mention P codes where the app had them; they are retired, see "P codes" in section 3.)

Each run is one agent, ≤ 90 minutes, ends with a build that passes `xcodebuild test` on the iPhone 18 Pro simulator and the flows report for its flows (from run 2 on), and stops. The orchestrator commits (`feat(app): …`, `feat(api): …`, `build(app): …`).

**Prerequisites (Jan, before run 1):**
1. `xcodebuild -downloadPlatform iOS` (the iOS 27.1 simulator runtime; nothing boots without it) and `brew install xcodegen`.
2. Team ID into `app/Team.xcconfig` (the orchestrator creates the file from the template).
3. App Store Connect: app record, API key in 1Password, Nikola's invitation (section 7). Needed by run 6, not before.
4. ~~Confirm Nikola's iPhone model and iOS version~~ Done: both phones run 27.1; the deployment target is 27.0 because of the simulator runtimes (section 1).
4b. Run 6 only: `xcodebuild -downloadComponent MetalToolchain` (the Metal Toolchain is not installed with Xcode 27.1 here; `xcrun metal` fails without it).
5. The greeting time zone (already pending from the v3 spec) and whether the `tips.py` dust may move once (section 4.2; default yes).
6. NFC stickers: NTAG213 or larger, 144 bytes is plenty.

**Server runs (the API worker; its files are `src/polished/api/`, `spec/`, `tests/test_api_*.py`, `scripts/make_api_fixtures.py`, `scripts/make_tip_fixtures.py`, one migration, and single-line touches in `server.py`, `auth.py`, `security.py`; the web runs own `templates/`, `static/`, `routes/`, `web.py`):**
- **S0 (30 min, first, before web run 1 or inside its brief since both edit `tips.py`):** split `tips.py` into `ops()` + `svg()`, `TipRandom` (SplitMix64), the two v3 tweaks, `DRAWING_VERSION` 3 and a hash-seed-independent `revision()`, `scripts/make_tip_fixtures.py`, `spec/tips/cases.json`, `spec/tips/random.json`, `spec/identifiers/*.json`; tests pass; the SVG for the pinned cases is byte-identical before and after the split (apart from the RNG change, which has its own test).
- **S1 (90 min):** Bearer gate, `008_api_tokens.sql`, `/auth/app/*`, `/api/v1/auth/*`, `/me`, `/home`, `/shades*`, `/bottles*` (GET), `/wishlist` (GET), `/wheels*` (GET), `/w/{slug}`, `/stacks/{id}` (GET), `/lookup`, `/identifiers` (GET), `/sync` (GET), the AASA route with `POLISHED_APPLE_TEAM_ID`, `/__test/reset`, `spec/api/openapi.yaml`, fixtures export, tests.
- **S2 (90 min):** every write endpoint of section 3, `/wear/{id}` with `009_wear.sql` and `wear.py`, the https sign-in callback (2.4), tests, fixtures for every write response (done in the S2 run; the web More page's Devices list is left to a web run). The deploy (image release, `POLISHED_APPLE_TEAM_ID` in the HelmRelease env) is Jan's after S2.

**App runs:**
1. **Skeleton and the painted tip** (needs S0): `project.yml`, targets, entitlements, Info.plist, `Team.xcconfig`, asset colours, Fraunces, `NailTips` (TipRandom, TipPainter, TipCanvas, TipShape, TipView with the static v3 light, LevelArc, Ledge, Rack, Ring geometry), the tab shell with placeholder screens showing fixture tips, the 1024 icon; Swift Testing: renderer parity, random vectors, GTIN vectors. Check: `xcodebuild test` green on iPhone 18 Pro; a debug gallery screen shows the 46 fixture tips at four sizes in light and dark (screenshot into the report dir).

   **Built (2026-10-26), where it differs from the plan:** `app/Scripts/test.sh` (xcodegen, `swift test` on the Mac, `xcodebuild test` on the iPhone 18 Pro / iOS 27.0, attachments exported with `xcresulttool` and renamed to `~/.cache/polished/native/<timestamp>/shots/`), `gallery.sh` (the gallery scrolled on the iPhone 18 Pro, iPad Pro 13" and iPhone Duo, light and dark, into `~/.cache/polished/native/gallery/`), `parity.sh` (web tips against the app's into `~/.cache/polished/native/parity.png`), `make_colours.py` (the palette catalog with Increased Contrast variants) and `make_app_icon.py` (the 1024 px flattened icon from `logo.svg`). The gallery and the parity screen are DEBUG-only (`-screen gallery`, `-screen parity`; the Debug build copies `spec/tips/cases.json` into the app as `TipCases.json`). `PolishedTests` compiles the package's test sources and gets `spec/` as a folder resource, so the same vectors run under `swift test` and `xcodebuild test`. `TipView`, `LevelArc`, `Ledge`, `Rack` and the tokens live in `Polished/Design/` (the widget target compiles that folder too), not in the package, which has no SwiftUI view code except `TipCanvas` and `TipShape`. The ring's geometry (the full wheel ring) is not built yet: only the `.ring` tip size exists; it arrives with the wheel page in run 2. The widget is a placeholder with a fixture shade. `PolishedAPI` has the `APIError` enum, the `PolishedAPI` protocol with `me()` and `Me`; `PolishedStore` an in-memory `SnapshotStore`; `PolishedModels` the `Tip`, `ShadeRow`, `Status`, `BottleState` DTOs and the identifier normalisers.
2. **Reading the collection** (needs S1 deployed or run against a local server): `PolishedAPI`, `LiveAPI` with ETags, `PolishedStore` snapshots, Session + Keychain + `ASWebAuthenticationSession` flow, Router and deep links, Home, Shades (search, marks, filters, Load more), Shade detail with the zoom transition, Bottles + History, Wishlist (read), Wheels list + the ring page (read), Settings; the flows harness (`flows.sh`, `report.py`, `/__test/reset`) with `search`, `tabs`, `history`, `deep-link`; the Duo pose investigation note. Check: flows green on the three simulators, light and dark.

   **Built (2026-10-26), where it differs from the plan:**
   - `PolishedAPI`: the protocol has two generic requirements, `get(_ endpoint:)` and `cached(_:)`, and `Endpoint<Value>` values (`Endpoint.home()`, `.shades(query)`, `.wheel(slug:)` …) name every GET; the named methods (`api.home()`, `api.shade(id:)`) are extension sugar, so a test double implements two functions. `LiveAPI` keeps its ETags in a `ResponseCache` (the SwiftData `SnapshotStore` implements it) and answers a 304 from the cached body. `FixtureAPI` reads `spec/api/fixtures/` by request path. The DTOs live in `PolishedModels` (snake_case through `APICoding`, not hand-written `CodingKeys`). The decoding test re-encodes each GET fixture and fails when any non-null key of the recording is missing from the DTO, which is the "unknown top-level keys" check applied at every depth; a second test fails when a GET fixture has no entry.
   - `PolishedStore`: `SnapshotStore` (SwiftData `@ModelActor`, key, ETag, body, fetch time, trimmed to 300 entries), `Session` with `KeychainTokenStore` (`AfterFirstUnlockThisDeviceOnly`) and `MemoryTokenStore`, `Router`, `Resource<Value>` (snapshot first, then the server; keeps the value and sets `error` when a refresh fails, which draws the "Showing what was here a moment ago" line) and `ShadeListModel` (page one plus Load more).
   - Screens: Home (greeting by the household time zone from `/me`, the search field, Wear today with "Another" working and "I wore this" absent until run 3, the rack, the wheel card with a 132 pt mini ring, the numbers, three links), Shades (`.searchable` with a 250 ms debounce, `marks` as an `AttributedString` wash through `Marks`, filters popover/sheet with a count badge, Load more as the last row), Shade detail (plate with a pool of the shade's own colour, photos, bottles with the level arc, facts, Swatched on, shop page in `SFSafariViewController`, zoom transition from the row, rack and hero tips), Bottles (Collection with level chips and Show archived, History by month with totals), Wishlist (head with the checkout link in `SFSafariViewController`, Copy list, the include control that re-queries `max_priority`, rows by priority), Wheels (cards with mini rings, Archived disclosure), Wheel (the 20-slot ring of real tips from `RingGeometry`, filled, empty and draft slots, the hub number, Swatches list, a read-only swatch sheet) and Settings (account, server, devices, catalog sync, version, sign out). iPad and the unfolded Duo use `NavigationSplitView` in Shades, Bottles and Wheels; Settings is a tab at the foot of the sidebar on a regular width and a sheet from Home's mark on a phone.
   - Sign-in: `ASWebAuthenticationSession` through SwiftUI's `webAuthenticationSession` environment value with `.https(host:path:)` on the server's host; PKCE in `PolishedAPI.PKCE`; exchange; a link that arrives signed out waits in `Router.pendingLink`. The sign-in itself needs the claimed associated domain and a real Pocket ID, so it is device-only; the flows cover the screen. Debug launch arguments (`LaunchOptions`): `-server`, `-token`, `-uitest`, `-open <url>`, `-signedout`, `-tab`, `-focussearch`.
   - Flows: `app/Scripts/flows.sh` (builds once with `build-for-testing`, starts the server of `Scripts/native_server.py`, which seeds `seed_native.py`: the e2e catalog plus the household of `scripts/make_api_fixtures.py` plus ten more swatches on Holos; each device is shut down and booted fresh first, then every flow runs in light and dark), `report.py` (the HTML report, exit 1 on a failed or missing flow), `Scripts/lib/server.sh` and `sim.sh`. Flows: `SearchFlow`, `TabsFlow`, `HistoryFlow`, `DeepLinkFlow` (launches with `-open`: `simctl openurl` cannot route an https universal link without the signed associated domain), plus `ShadeDetailFlow`, `WheelFlow`, `WishlistFlow` and `SignInFlow`. `test.sh` starts the same server and runs all of them on the iPhone 18 Pro.
   - Deferred: the Settings "Sync now" and learned codes (writes and run 5), the Duo `ArrangementView`/reserved-region layouts (run 6), the pose investigation result is in section 6.2.
3. **Writes** (needs S2): Add/edit bottle sheet (level, date presets, price, P code under More details), level chips, archive and delete, wishlist heart, priority, note, remove, checkout (`SFSafariViewController`), Copy list, I bought these, wheel create/rename/archive/delete/new URL/take tag, tip colour (`ColorPicker`), manual shade, I wore this + Another, the arrival moment and the haptics map. Flows: `add-bottle`, `bottle-level`, `wishlist`, `wheel-delete`.
   **Built (2026-10-27), where it differs from the plan:**
   - `PolishedAPI`: one generic `send(_ request: Request<Response>)` carries every write (`Request.addBottle`, `.updateBottle`, `.wish`, `.bought`, `.setTipColour`, `.wear`, `.createWheel`, `.deleteWheel`, `.takeTag`, `.runSync` …); `Patch<Value>` encodes a PATCH key as left out, `null` or set. `APIError.timeout` is split from `.offline` so a toggle retries only timeouts. `FixtureAPI` answers a write from its recording; each write fixture has a test that the request the app builds is the recorded one and the answer decodes without dropping a key. The builder's stack writes, identifiers and the sign-in fixtures are listed as later in `WriteFixtureTests`.
   - `PolishedStore.WriteCoordinator`: `toggle` (optimistic: apply, send in order per lane, one retry after 2 s on a timeout, revert plus a status line on failure), `perform` (awaits the server), `changeLevel`; every success invalidates the snapshots named by a `WriteEffect` and raises `revision`, which `revalidating` reloads on. `SaveAction` shows its progress state only after 300 ms and splits a 422's `fields` per input.
   - UI: Add/Edit bottle sheet (a `LevelPicker` with the arcs, native `DatePicker` with Today / Yesterday / Don't know, price field in dollars sent as cents, P code, opened on and notes under More details, Archive, Delete with a confirmation), the level menu on every bottle row, the heart on shade detail and on shade rows (swipe, context menu), priority menu, note, remove and "I bought these" on the wishlist, wheel create, rename with Archive under it, a red Delete sheet that counts the swatches, New tag URL, Take the tag of…, tip colour (system `ColorPicker`, a hex field that selects all on edit, Reset), manual shade, Home's "I wore this" and "Another", Sync now with its 202, 409 and 429 sentences, and the arrival moment (spring scale plus one specular sweep; Reduce Motion: opacity only) with the haptics of 5.8.
   - Flows: `AddBottleFlow`, `BottleLevelFlow`, `WishlistWritesFlow`, `WheelDeleteFlow`, plus `WheelTagFlow` (run 5 replaced it with `TagFlow`), `WearFlow` and `TipColourFlow` (the system colour picker is a remote view XCUITest cannot drive, so the flow sets the colour through the hex field). `flows.sh` and `test.sh` delete their `.xcresult` bundles after exporting and keep only the newest report.
4. **The builder**: sheet with detents on compact, inspector on regular, `ArrangementView` on the Duo behind `#available`, every stack operation with optimistic coats/move, the picker with scopes and the P-code suggestion row, templates, Copy from… list, name/note/date, save with the sweep, cancel, remove swatch, resumed drafts, `?hl` from Swatched on. Flow: `builder`.
   **Built (2026-10-27), where it differs from the plan:**
   - `PolishedStore.BuilderModel` holds the draft (`StackSheet`) and the picker. Coats, move and remove apply at once and go to the server in the order they were made; the answer replaces the sheet only when no edit is still waiting, so three quick taps on + never bounce back. Adding a layer and the three templates wait for the server (the new layer's id is the server's); the + of the tapped row shows a spinner meanwhile. A refused edit (`stack_full`, a 409) says why in a line under the head and reloads the sheet. Eight layers are also refused before the request. `Request.openDraft`, `.addLayer`, `.changeCoats`, `.moveLayer`, `.removeLayer`, `.template`, `.saveStack`, `.cancelStack`, `.clearSlot` carry the writes; `StackSheet` gained the optional `resumed` and `result` of the draft and template answers; every stack write fixture has a request test. `WriteCoordinator.didWrite` skips an empty effect.
   - Shells: a sheet (`.medium`/`.large`, opening at `.large`, background interaction up to `.medium`) on a compact width, an `.inspector` (360 to 400 pt) on a regular width. They are exclusive (`if compact { sheet } else { inspector }`): a sheet and an inspector on the same view made the whole wheel page pop when the sheet opened. An inspector has no navigation bar, so its Close (keeps the draft; there is no grabber), Cancel and Save swatch sit in the pane; the sheet uses the bar's `.cancellationAction` and `.confirmationAction`. On the iPad in portrait the system draws the inspector over the detail column (dimmed) instead of beside it; in landscape it sits beside the ring.
   - The head (composite tip with a crossfade, "Slot 11", the wheel, "Resumed your draft.", the summary) and the refusal line are pinned above the scrolling list, so the composite answers every tap while the picker is scrolled into view.
   - The picker is a plain field with `@FocusState`, not `.searchable`: the wireframe puts it between the templates and the results, and a toolbar field would take the layers out of view. Typing a P code shows the suggestion row first. A tap on a row adds the layer and clears the field (the web does the same); the keyboard stays.
   - Copy from… is a nested sheet with `.searchable` and a "Replace the layers?" confirmation when the draft has layers. Same as last answers `nothing_saved` with the warning haptic and a line.
   - A saved slot's Remove swatch is a red row at the foot with a confirmation. Cancel (bar or pane) discards the draft; dragging the sheet away or Close keeps it, and the ring shows the draft's dashed edge.
   - The ring: the slot being edited has an ink ring, the one saved has the sweep once the builder has closed (with the success haptic), `highlighted` (foil) comes from `Route.wheel(slug:highlight:)`, which a shade's Swatched on pushes. The read-only `SwatchSheet` is gone: every slot opens the builder.
   - Not built: the `ArrangementView` split of the Duo's inner display. Unfolded, the Duo is a regular width and gets the inspector like the iPad; the simulator's default pose is the compact one, so the flows exercise the sheet there.
   - Flows: `BuilderFlow` (slot 11, which is empty in the seed; slot 12 is filled and Over black would answer "Already over black"), `BuilderCopyFlow`, `BuilderResumeFlow`. `flows.sh --duo-also A,B` adds flows to the Duo run only; `report.py` reads each run's flow list from its json.
   - Also: the delete-wheel sheet leaves out "its 0 swatches"; the Add bottle sheet names the shade in the navigation subtitle and gives its header row a top inset.
5. **Scan, tag, NFC, widget**: `DataScannerViewController` wrapper, the Scan screen and its outcomes, learn and learned codes, the Tag page with the native QR, the Core NFC write and check flows with every failure state, the "Wear today" widget with the App Group snapshot, Home's Scan button, the manual checklist as `docs/NATIVE-CHECKLIST.md`. Flows: `scan-typed`, `tag-page`.
   **Built (2026-10-27), where it differs from the plan:**
   - Core: `PolishedStore.ScanModel` is the Scan screen's state (`ScanPhase`: one case for each outcome of `GET /lookup`, plus looking and failed). A barcode from the camera is normalised first (`Identifiers.normaliseGTIN`: check digit, length) and a misread is "Couldn't read that reliably" without a request; typed text goes to `/lookup?via=typed` as it is. The camera reports one bottle many times a second, so the same code is asked about once. `learn` is `POST /identifiers` (`Request.learn`, `.forgetCode`, `WriteEffect.codeChange`; both have write-fixture tests), and `forget` ("This isn't it") asks again, which now says the code is new. `PolishedModels.StickerVerdict` words what a sticker's link opens (this wheel, another by name, a wheel that is gone, a shade, not ours, blank). `Router.tagSlug` keeps the Tag sheet's wheel and follows a new address or a swap.
   - Scan: `ScanScreen` is a full-screen cover (`scanCover`) from Home's barcode button, the Bottles bar and the builder's picker (there a match is **Add layer**, not Add bottle). `DataScannerViewController` (EAN-13, EAN-8, UPC-E; a UPC-A reads as EAN-13; Code 128 off) with highlighting, guidance, pinch zoom, a framing guide that turns green on accept with the rigid haptic, a torch and Close on glass. Without a camera (`isSupported` false: simulators) or without access (`isAvailable` false: a line and **Allow camera access in Settings**, which opens `UIApplication.openSettingsURLString`) the typed field stands alone. The card: match (bottle photo, painted tip, finishes, price; Add bottle, This isn't it with a confirmation), suggestion ("Is it Spirit Fingers?" with Yes, add a bottle, and a picker for the other shade), unknown barcode and unknown P code (a catalog search; picking one learns, then the card is the match with "Saved. … is now …" and Add bottle), invalid (scanned or typed wording of the web), results (rows that open the shade) and failed. A P code rides into the Add bottle form (`BottleSheetMode.add(_, printedCode:)`). After a bottle is added from the scan screen the cover closes with "Added <shade>". The learned codes screen is under Settings and under the Scan screen.
   - Tag: the foot of the wheel page has **Tag and QR** (New tag URL and Take the tag of… moved into it, under "Move the tag"). The sheet: CoreImage QR (level M, whole pixels per module, `interpolation(.none)`, on a white plate in dark mode too), the address with Copy and ShareLink, **Write to sticker** and **Check the sticker** when `NFCNDEFReaderSession.readingAvailable` (the lede says "Write it from your iPhone" when not), the outcome line, and "Written <date>" kept in UserDefaults by slug (a new tag URL starts again, a swap swaps the dates). Core NFC sits behind `StickerService` (`CoreNFCStickers`: connect, `queryNDEFStatus`, capacity, writable, `writeNDEF`, read back and compare, never `writeLock`; every failure has its sentence); a Debug build launched with `-nfc ok|other|readonly` uses an in-memory sticker (`FakeStickers`).
   - iPad: the split views (Shades, Bottles, Wheels) fold their list column away while the builder is open and restore it afterwards (`collapsesSidebarForBuilder`, driven by `AppModel.builderIsOpen`), so the ring has the room.
   - Universal links: `onOpenURL` and `onContinueUserActivity(NSUserActivityTypeBrowsingWeb)` both feed `Router.handle` (idempotent, so a link that reaches both is harmless); a link while signed out waits in `pendingLink` and the last one wins. Unit tests cover warm, repeated and signed-out links. A real tap needs the signed associated domain (device-only, section 6.3); the flows launch with `-open`.
   - Not built in run 5: the "Wear today" widget (its App Group snapshot) and a separate `NATIVE-CHECKLIST.md` (the checklist is section 6.3).
   - Flows: `ScanTypedFlow`, `TagFlow` (replaces `WheelTagFlow`), `TagStickerFlow` (the fake sticker: blank, written, read back, locked, another wheel). The seed already teaches `0810170284120` to Spirit Fingers, so the flow forgets it first to reach the unknown-barcode card.
6. **Light, Duo polish, accessibility, TestFlight**: `TipLight.metal` + `TipLightModel` with the gates and an Instruments pass, reserved-region handling on the ring page, the four-column Wheels grid, Dynamic Type and VoiceOver audit against 5.10 (fix what the AX pass of the flows shows), Increase Contrast pass, icon layers for Icon Composer, `archive-upload.sh`, `bump-build.sh`, `ExportOptions.plist`, the first archive. Jan runs the upload (or approves the agent's blocked command), then the device checklist.
   **Run 6a (2026-10-27, "ready for TestFlight"), what was built:**
   - Scan: the line for a device that cannot scan (simulators) was set in ink-2 on the Fill panel with the icon in ink-3 (a light-on-light render seen in run 5's screenshots did not reproduce on a fresh simulator; the code is unchanged apart from the sentence); the denied case ("Camera access is off for Polished. Allow it in Settings, or type the digits below.") has the button **Allow camera access in Settings**, which opens `UIApplication.openSettingsURLString`.
   - iPad: the three split views (Shades, Bottles, Wheels) now start with both columns (`NavigationSplitViewVisibility.all`, `.balanced` style). With `.automatic` an iPad in portrait opened on the detail's placeholder with the list hidden behind the sidebar button, which also failed `SearchFlow`, `AddBottleFlow` and `BottleLevelFlow` on the iPad; the list is there again and the builder still folds it (`collapsesSidebarForBuilder`).
   - `BuilderFlow` on an iPad opens the builder in portrait (the list column is folded, the inspector beside the ring), closes it keeping the draft, turns the device to landscape (`XCUIDevice.shared.orientation = .landscapeLeft`), opens slot 11 again (`opened-landscape`) and turns back. `FlowCase.setUp` puts the device upright first so one flow cannot leave the next sideways. Turning the iPad **while the builder is open** closes it (the draft is kept on the server, "Resumed your draft." on the next open); not fixed in 6a. XCUITest's landscape screenshot on the iPad simulator is the portrait buffer with the landscape layout drawn rotated and cropped, so read the landscape step with that in mind.
   - Release: `CFBundleShortVersionString` and `CFBundleVersion` come from the build settings (they were XcodeGen's literal `1.0` and `1`, which would have ignored `bump-build.sh`), `Build.xcconfig` carries the build number, `PrivacyInfo.xcprivacy` is in the app, `ExportOptions.plist`, `archive.sh`, `bump-build.sh`, `upload.sh` exist (section 7).


**Parallelism and boundaries:** S0 → (S1 ∥ app 1) → (S2 ∥ app 2) → app 3 → app 4 → (app 5 ∥ app 6's shader half, if two agents are available; otherwise in order). The web's phase-1 runs 1–3 proceed in parallel throughout: they never touch `app/`, `spec/` or `src/polished/api/`; the only shared files are `tips.py` (S0, coordinated into web run 1) and the `wear` migration (web run 3 and S2 agree on the file name in their briefs). `DESIGN.md` gains a section 17 "API and the native app" in S1 and `docs/NATIVE.md` (this spec) is updated at the end of each app run where the build departs from it.

---

## 9. Flagged: could not verify

- **iPhone Duo simulator poses from the command line** (folded/unfolded, partially folded): investigated in run 2, there is none (section 6.2); poses are GUI-only in Device Hub.
- **`.sidebarAdaptable` on the Duo inner display**: whether the tab bar becomes a sidebar there is undocumented; the design works either way.
- **Core NFC on iPhone Duo**: assumed present (Apple Pay); the Tag page hides Write when `readingAvailable` is false, so a surprise degrades gracefully.
- **Fraunces tabular figures** (`tnum`): checked in run 1, absent; the frame-based fallback is in `DisplayNumber`.
- **Apple's AASA CDN through the Cloudflare tunnel**: the `app-site-association.cdn-apple.com/a/v1/polished.janpuc.com` check in the manual list proves it; if Cloudflare's bot rules block the fetch, a WAF skip rule for `/.well-known/apple-app-site-association` is the fix (home-ops, Jan).
- **App Store Connect name "Polished"**: availability unknown until Jan creates the record.
- **`ArrangementView` inside an inspector or sheet**: used only at the screen level (HIG: keep navigation outside it), so this does not block anything.
- **Shader cost with 40 live ring tips**: measured in run 6; the fallback is static light on the ring.

## 10. Sources

Apple newsroom: [Apple unveils iPhone Duo (2026-09-09)](https://www.apple.com/newsroom/2026/09/apple-unveils-iphone-duo/) (5.4" outer, 7.6" inner, same aspect ratio, iOS 27 side controls, Split View on iPhone, continuity across displays, Device Hub support in Xcode); [Developers bring new app experiences to iPhone Duo (2026-10-22)](https://www.apple.com/newsroom/2026/10/developers-bring-incredible-new-app-experiences-to-iphone-duo/) (partially folded poses, "Made for iPhone Duo" badge). Apple developer: [Get ready for iPhone Duo](https://developer.apple.com/iphone-duo/) (Xcode 27.1 is the SDK); HIG [Designing for iPhone Duo](https://developer.apple.com/design/human-interface-guidelines/designing-for-iphone-duo) (compact outer / regular inner, reserved regions, arrangement views, vertical controls, even column counts); [Preparing your app for iPhone Duo](https://developer.apple.com/documentation/technologyoverviews/preparing-your-app-for-iphone-duo) (bars vertical in sheets on the outer display, `toolbarVerticalBehavior`, `presentationPlacement`, `toolbarVerticalEdge`); [ReservedRegion](https://developer.apple.com/documentation/swiftui/reservedregion) and [`reservedRegions(kind:options:layoutDirectionBehavior:)`](https://developer.apple.com/documentation/swiftui/geometryproxy/reservedregions(kind:options:layoutdirectionbehavior:)) (iOS 27.1); [ArrangementView](https://developer.apple.com/documentation/swiftui/arrangementview) (27.1); [ToolbarItemVisibilityPriority](https://developer.apple.com/documentation/swiftui/toolbaritemvisibilitypriority) (27.0); [Device Hub](https://developer.apple.com/documentation/xcode/device-hub). SwiftUI availability (documentation JSON): [`glassEffect(_:in:)`](https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)), [GlassEffectContainer](https://developer.apple.com/documentation/swiftui/glasseffectcontainer), [`glassEffectID`](https://developer.apple.com/documentation/swiftui/view/glasseffectid(_:in:)), [`tabBarMinimizeBehavior`](https://developer.apple.com/documentation/swiftui/view/tabbarminimizebehavior(_:)), [`searchToolbarBehavior`](https://developer.apple.com/documentation/swiftui/view/searchtoolbarbehavior(_:)), [`scrollEdgeEffectStyle`](https://developer.apple.com/documentation/swiftui/view/scrolledgeeffectstyle(_:for:)), [`backgroundExtensionEffect`](https://developer.apple.com/documentation/swiftui/view/backgroundextensioneffect()) (all iOS 26); [`sidebarAdaptable`](https://developer.apple.com/documentation/swiftui/tabviewstyle/sidebaradaptable), [`navigationTransition`](https://developer.apple.com/documentation/swiftui/view/navigationtransition(_:)), [`zoom(sourceID:in:)`](https://developer.apple.com/documentation/swiftui/navigationtransition/zoom(sourceid:in:)), [`matchedTransitionSource`](https://developer.apple.com/documentation/swiftui/view/matchedtransitionsource(id:in:)), [`presentationSizing`](https://developer.apple.com/documentation/swiftui/view/presentationsizing(_:)), [TabRole.search](https://developer.apple.com/documentation/swiftui/tabrole/search) (iOS 18); [`presentationDetents`](https://developer.apple.com/documentation/swiftui/view/presentationdetents(_:)) (16); [`inspector`](https://developer.apple.com/documentation/swiftui/view/inspector(ispresented:content:)), [`sensoryFeedback`](https://developer.apple.com/documentation/swiftui/view/sensoryfeedback(_:trigger:)), [`colorEffect`](https://developer.apple.com/documentation/swiftui/view/coloreffect(_:isenabled:)), [`layerEffect`](https://developer.apple.com/documentation/swiftui/view/layereffect(_:maxsampleoffset:isenabled:)), [`distortionEffect`](https://developer.apple.com/documentation/swiftui/view/distortioneffect(_:maxsampleoffset:isenabled:)), [ShaderLibrary](https://developer.apple.com/documentation/swiftui/shaderlibrary), [SwiftData](https://developer.apple.com/documentation/swiftdata) (17); [NavigationSplitView](https://developer.apple.com/documentation/swiftui/navigationsplitview), [Canvas](https://developer.apple.com/documentation/swiftui/canvas), [`onOpenURL`](https://developer.apple.com/documentation/swiftui/view/onopenurl(perform:)). Frameworks: [NFCNDEFReaderSession](https://developer.apple.com/documentation/corenfc/nfcndefreadersession), [`writeNDEF`](https://developer.apple.com/documentation/corenfc/nfcndeftag/writendef(_:completionhandler:)), [NFC formats entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.nfc.readersession.formats), [Adding support for background tag reading](https://developer.apple.com/documentation/corenfc/adding-support-for-background-tag-reading) (universal link in the first URI record launches the app; Safari otherwise); [DataScannerViewController](https://developer.apple.com/documentation/visionkit/datascannerviewcontroller) and [`isSupported`](https://developer.apple.com/documentation/visionkit/datascannerviewcontroller/issupported); [ASWebAuthenticationSession.Callback](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsession/callback) and [`https(host:path:)`](https://developer.apple.com/documentation/authenticationservices/aswebauthenticationsession/callback/https(host:path:)) (needs an associated domain); [Supporting associated domains](https://developer.apple.com/documentation/xcode/supporting-associated-domains); [Supporting universal links in your app](https://developer.apple.com/documentation/xcode/supporting-universal-links-in-your-app); [CMMotionManager](https://developer.apple.com/documentation/coremotion/cmmotionmanager); [WidgetKit](https://developer.apple.com/documentation/widgetkit), [StaticConfiguration](https://developer.apple.com/documentation/widgetkit/staticconfiguration); [App Intents](https://developer.apple.com/documentation/appintents) (cut from v1); [Swift Testing](https://developer.apple.com/documentation/testing). Materials and icon: [Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/liquid-glass), [Adopting Liquid Glass](https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass) ("a distinct functional layer for controls and navigation elements"), [Creating your app icon using Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer), HIG [App icons](https://developer.apple.com/design/human-interface-guidelines/app-icons) (flattened image allowed). Distribution: [Add internal testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/add-internal-testers) (roles Account Holder, Admin, App Manager, Developer, Marketing; 100 testers), [Invite external testers](https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers), [Upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds) (Xcode, altool, Transporter), [Distributing your app for beta testing and releases](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases). Fonts: [Fraunces](https://github.com/undercasetype/Fraunces) (`fonts/ttf/Fraunces144pt-SemiBold.ttf`, OFL 1.1). Local checks: `xcodebuild -version`, `-showsdks`, `-help`; `xcrun simctl list devicetypes|runtimes`; `xcrun simctl ui`; `xcrun xcresulttool export attachments --help`; `xcrun altool --help`; `brew info xcodegen`.
