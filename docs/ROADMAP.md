# polished: roadmap

Decided with Jan on 2026-10-26. Phases 1 and 2 are being built now; phase 3 is written down so the
ideas are not lost, and nothing in phases 1 and 2 should make it harder.

## Phase 1: the self-hosted web app, great for one household (now)

The FastAPI + HTMX app at polished.janpuc.com, behind Pocket ID, Holo Taco as the only catalog.

- Fuzzy search (ranking plus typo tolerance), delete a wheel with confirmation, observable end-to-end
  flows (`tests/e2e/run_flows.py`, iPhone, iPad and Mac profiles, light and dark, screenshot report).
- Visual v3 on the web (design spec by Fable): the Mac layout above all, since the native app takes
  over on iPhone and iPad; quieter P code, a better level indicator and date field.
- NFC on the web stays "copy the link, write it with NFC Tools"; the native app does it properly.

## Phase 2: a native app for the two of us (now)

A SwiftUI app for iPhone, iPad and iPhone Duo (iOS and iPadOS 27), a client of our own server,
distributed through TestFlight to Jan and Nikola only. The Mac keeps the web app (and the iPad app runs
on Apple Silicon Macs as "Designed for iPad" at no extra cost).

- Server: a JSON API (`/api/v1`), app sign-in through the existing Pocket ID flow in an
  `ASWebAuthenticationSession` ending in a long-lived per-device API token, and
  `/.well-known/apple-app-site-association` so `https://polished.janpuc.com/w/<slug>` opens the app.
- NFC: Core NFC writes the wheel's https address to a sticker from inside the app; tapping the sticker
  opens the app straight on that wheel through the universal link (Safari only when the app is not
  installed).
- Barcode scanning with VisionKit's live scanner; native date pickers, sheets, haptics.
- The painted tips rendered natively (a SwiftUI port of `tips.py`), with tilt-reactive holo and gloss
  (Core Motion driving a shader), so the collection reads as lit, precious objects.
- Layouts that adapt to every size class: the folded and unfolded iPhone Duo, iPad split views.

## Phase 3: publishing (later, only if we decide to)

Written down, not designed in detail.

- **Two products.** An open-source, self-hostable server with its web UI, complete on its own and free
  (AGPL, so nobody runs it as a closed hosted service). The native app: free as a client of the user's
  own server; a one-time in-app purchase (StoreKit 2 non-consumable, restore purchases, Family
  Sharing) unlocks standalone mode, with an on-device engine and the user's own iCloud (CloudKit) and
  no server. A free tier that needs your own server is accepted on the App Store (Home Assistant and
  Jellyfin work this way).
- **No brand data shipped by us.** Brands are catalog sources the user chooses to add ("Which brands
  do you collect?", with a not-affiliated notice); the user's server or device fetches the brand's
  public store. We maintain a curated registry of compatible source definitions (how to fetch and
  parse, no brand data), starting with a generic Shopify adapter and Holo Taco.
- **Colour hints.** A scheduled job of ours runs the colour sampler and our hand-checked corrections
  and publishes per source a file with no names, brands, links or images: opaque keys (a truncated
  SHA-256 of a product identity the client can compute itself, such as
  `shopify:<shop-domain>:<product-id>`) mapped to `{hex, hex2, version}`. Clients download the whole
  file per source (it reveals nothing about anyone's collection), use a hint when present, sample
  locally when there is none or the image changed, and the user's own override always wins.
- **User-made brands and shades** are first-class everywhere (bottles, wishlist, wheels, layer
  stacks, search), in both modes. When a brand a user added by hand becomes a curated source, a
  reconcile flow proposes matches (fuzzy names with confidence, manual pairing for the rest), shows a
  preview, and per shade or in bulk keeps the user's colour or takes the provided one, re-pointing
  bottles, stacks, wheel slots, wishlist entries and learned codes. Nothing is lost.
- **Colour customisation on every shade**, catalog ones included (colours and finish effects of the
  tip, reset to provided); overrides survive catalog refreshes and colour-hint updates.
- **Self-host auth.** Built-in accounts (passkeys or a password) by default, any OIDC provider
  (Pocket ID, Authelia, Authentik) as an option, no-login for a single user on a LAN. The app pairs
  with a server by scanning a QR code from the web UI that grants a scoped API token.
- **Two engines in step.** The Python engine (server) and the Swift engine (app) share JSON
  conformance fixtures under `spec/`: catalog parsing, colour sampling tolerances, tip rendering,
  search ranking, layer rules.
- **Portable collection format** for export and import, used to move between modes and servers.
- **App Store.** Guideline 5.2 (third-party IP) is why nothing brand-specific ships in the binary;
  consider asking Holo Taco for their blessing before going public.

### Requests noted by Jan on 2026-10-27 (not designed, not built; the MVP comes first)

- **Multi-brand with a curated catalog.** Polished has to work across brands, and the shade to
  colour mapping is curated by us, not left to each user. The identity of a bottle is what every
  brand has: **brand + name + barcode**. Brand-specific oddities such as Holo Taco's printed P codes
  are dropped as an identifier (they don't exist elsewhere and would only confuse matching).
  Identification is "scan the barcode and you're done".
  The P codes were wiped from the server and the web on 2026-10-28 (DESIGN 14 item 88); the app follows.
- **Crowdsourced identification.** When a scanned barcode is unknown, the user labels it (brand,
  shade, maybe a photo or a colour) and that submission comes back to us. One report is a strong
  signal, not proof (people make mistakes), so submissions are weighed (several agreeing reports,
  reporter history) and curated before they enter the shared catalog. The same path fills missing
  barcodes and colours. Needs consent and a privacy statement; ties into the colour hints above.
- **Curated wheel models.** Users don't type "20-nail wheel": they pick from a curated list of
  swatch wheels that actually exist (slot count, ring geometry, shape, maybe the maker), and the
  visualization follows the model. A custom slot count stays possible as an override.
- **Single-nail swatches.** Besides wheels, support swatches on single nails, e.g. nail strips on a
  keychain ring, with their own visualization. Identifying them needs something other than one NFC
  tag per nail (wasteful) or a QR per nail (tedious). Options to evaluate: one tag or QR per
  keychain/strip with numbered positions; tiny printed codes (Data Matrix or a short number) on the
  back of each nail; recognising the nail from a photo by its colour and finish against her own
  swatches (on-device); or picking from a short list filtered by colour family. Open question.
- **Hand view.** A preview of a planned mani on a hand: five fingers (or two hands), each nail
  assigned a shade or a layer stack, like the wheel builder but for what she would paint, with
  accent nails and patterns. Uses the same tip renderer, drawn on nail shapes of a hand.

### What phases 1 and 2 avoid so phase 3 stays open

- No new Holo Taco specifics beyond today's catalog adapter (keep brand rules in `catalog/`).
- The JSON API and its data shapes are written as the contract a future standalone engine and other
  servers will also meet: no web-only assumptions in it.
