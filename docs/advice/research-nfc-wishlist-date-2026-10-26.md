# Research: polished — NFC writing, Holo Taco wishlist, iOS date input

Date of research: 2026-10-26. Holo Taco contact: 3 GETs total (homepage HTML, `base.bundle.min.js` theme asset, `/pages/wishlist` logged-out HTML). No login, no API calls to the wishlist service.

## Summary
1. **NFC:** No documented URL scheme prefills a write in NFC Tools, NXP TagWriter or NFC.cool. The only documented way to launch a prefilled write is NFC.cool Tools' **"Write NFC" App Intent** (Shortcuts), which Safari can trigger via `shortcuts://run-shortcut?...&input=text&text=<url>`. A free native app is not possible (NFC entitlement needs the paid program). Recommended: Shortcut + NFC.cool, with fallback of a copy-URL button plus a manual paste into NFC Tools. Also offer a printable list or QR.
2. **Wishlist:** holotaco.com uses a **custom in-house wishlist**, not a Shopify app. The theme JS talks to `https://wishlist.holotaco.com/api/v1/wishlist` and supports a share-code mode (`?id=<shareCode>`), but I could not find a user-visible share-link UI or the share page URL format. Most robust import: a **bookmarklet or console snippet run on her logged-in wishlist page** that reads product handles from the DOM and POSTs them to polished. Fallback is paste text or links.
3. **Date input:** Use the overlay pattern (a styled button/label over a real, transparent `<input type=date>`), plus `appearance:none` and `box-sizing:border-box` on any visible native date input. Add Today/Yesterday presets as real buttons. Do not rely on `showPicker()` on iOS.

---

# 1. NFC tag writing from iPhone

## Findings

1. **Claim:** NFC Tools (wakdev, iOS) has no documented URL scheme to launch or prefill a write. Wakdev reportedly said a direct scheme was planned but "not available yet". Writing is in-app only: Write → Add a record → URL/URI → Write → tap the tag.
   **Sources:** [Reddit r/nfctools "Is there a URL scheme for triggering NFC Tools?"](https://www.reddit.com/r/nfctools/comments/18p8q4d) (via search snippet; the page itself would not fetch), [wakdev how-to](https://www.wakdev.com/en/knowledge-base/how-to-guides/how-to-write-a-link-url-on-an-nfc-chip.html).
   **Support:** interpretation (absence of documentation plus a secondhand quote). **Confidence:** medium.

2. **Claim:** NFC TagWriter by NXP: I found no URL scheme or x-callback-url documentation (user manual and App Store page only show in-app flows). Its App Store reviews include a 2023 report of a bug when writing URLs.
   **Sources:** [NXP user manual](https://inspire.nxp.com/tagwriter/tag-writer-user-manual.pdf), [App Store listing](https://apps.apple.com/us/app/nfc-tagwriter-by-nxp/id1246143221). **Support:** absence of evidence. **Confidence:** medium-low. I did not check Simply NFC, which is likewise unverified.

3. **Claim:** **NFC.cool Tools** (iOS) exposes a **`Write NFC` App Intent** that "opens the NFC write flow pre-filled with a URL or a text payload supplied by the Shortcut". Its documented URL schemes (`nfcforiphone://scan-nfc|scan-code|scan-document|scan-object|scan-room`) only open scanners; there is none for write. The write flow stays in the app. Nothing documents an automatic return to Safari. Whether "Write NFC" is free or Pro is not stated on the developer page.
   **Sources:** [NFC.cool developers page, "App Intents & Shortcuts" and "URL schemes"](https://nfc.cool/developers/), fetched directly. **Support:** direct evidence. **Confidence:** high for existence, low for pricing and return behaviour.

4. **Claim:** Apple Shortcuts has **no native "write NFC tag" action**. Its NFC support is a *trigger* (an automation runs when a tag is scanned, keyed on tag identity). A public wishlist item (June 2025) asks for a write action. Third-party apps can supply the action (NFC.cool above). I found no evidence that NFC Tools exposes Shortcuts actions.
   **Sources:** [Luke's Apple Wishlist: "Shortcuts action: read/write NFC tags", 2025-06-23](https://apple.lukezilioli.com/wishlist/shortcuts-nfc-action/), [Apple StackExchange](https://apple.stackexchange.com/questions/442457/possible-to-read-text-record-from-nfc-tag-within-shortcuts), [NFC.cool features](https://nfc.cool/features/nfc-reader-writer/). **Support:** interpretation. **Confidence:** medium.

5. **Claim:** Safari can launch a Shortcut with a text input using Apple's documented URL scheme: `shortcuts://run-shortcut?name=[name]&input=text&text=[url-encoded text]`. Example from Apple: `shortcuts://run-shortcut?name=Lookup%20Goetta&input=text&text=goetta%20is%20great`.
   **Sources:** [Apple Support: Run a shortcut using a URL scheme](https://support.apple.com/guide/shortcuts/run-a-shortcut-from-a-url-scheme-apd624386f42/ios), fetched directly. **Support:** direct evidence. **Confidence:** high.
   The user needs the shortcut installed first. Only Jan can create it and publish an iCloud link (`https://www.icloud.com/shortcuts/<id>`). Neither the app nor I can generate that link.
   *Researcher inference, not tested:* if the shortcut is `Receive Text input → NFC.cool "Write NFC" (URL = input)`, then the whole flow is one tap on the swatch page (opens Shortcuts → NFC.cool write screen → hold phone to the sticker). Check on a real iPhone whether it returns to Safari. The `x-success` callback form of the scheme (`shortcuts://x-callback-url/run-shortcut`) may help return, but I did not verify that.

6. **Claim:** A custom Core NFC app needs the paid Apple Developer Program. Apple's capability matrix lists "Near Field Communication (NFC) Tag Reading" and defines three tiers (ADP paid, ADEP enterprise, free "Apple Developer", where the free tier "can't distribute apps"). The table's per-tier tick marks were lost in extraction, so the NFC row's tier is not verified from the page itself. Secondary answers (search summary) say the free Personal Team cannot provision it.
   **Sources:** [Apple: Supported capabilities (iOS)](https://developer.apple.com/help/account/reference/supported-capabilities-ios), [Apple: Building an NFC tag-reader app](https://developer.apple.com/documentation/corenfc/building-an-nfc-tag-reader-app). **Support:** interpretation. **Confidence:** medium. Confirm in Xcode, which will show the capability as unavailable for a Personal Team.
   What it takes: Xcode, a physical iPhone 7 or newer, the NFC Tag Reading capability, an `NFCReaderUsageDescription` in Info.plist, and an `NFCNDEFReaderSession(invalidateAfterFirstRead: false)`. Then connect the tag, check `queryNDEFStatus == .readWrite`, and call `writeNDEF`. The Swift part is roughly 60–100 lines. Installing for others needs TestFlight (paid, 90-day builds); a free account's own-device builds expire after 7 days.
   **Sources:** [WWDC19 session 715](https://developer.apple.com/videos/play/wwdc2019/715/).

7. **Claim:** App Clips are not a good write path. Core NFC is a read/write API for full apps. In an App Clip, NFC is the *invocation* mechanism, and I found no evidence that NDEF writing works there.
   **Sources:** [Apple App Clips support](https://support.apple.com/guide/iphone/use-app-clips-iphb3a73ec53/27/ios/27) (via search summary). **Support:** inference. **Confidence:** low.

8. **Claim:** The tag payload should be a plain `https://` URL. iOS background tag reading handles only basic record types (https URL, tel, sms) and does not support custom URL schemes. So `https://polished.janpuc.com/w/abc123` works with a bare tap; a custom scheme tag would not.
   **Sources:** [Apple: Adding support for background tag reading](https://developer.apple.com/documentation/corenfc/adding-support-for-background-tag-reading), [wakdev: why iPhone doesn't react to some records](https://www.wakdev.com/en/knowledge-base/troubleshooting/nfc-tools-ios-why-my-iphone-doesnt-react-to-some-nfc-records.html). **Support:** direct (via search summaries). **Confidence:** medium-high.

9. iPad has no NFC, and Mac and Android are out of scope.

## Recommendation
- **Primary:** NFC.cool Tools plus a Jan-built Shortcut named "Write polished tag" (input: text → "Write NFC" with that URL). On the swatch page, show a "Write to sticker" link `shortcuts://run-shortcut?name=Write%20polished%20tag&input=text&text=<urlencoded https://polished.janpuc.com/w/abc123>`. Show it only on iPhone (user-agent check), with a short "first time: install this shortcut" link to the iCloud URL. Smoke-test first on an iPhone: does NFC.cool's write flow prefill, require Pro, and stay in the app?
- **Fallback:** a "Copy link" button plus instructions for NFC Tools (free: Write → Add a record → URL → paste → Write), using `navigator.clipboard.writeText`.
- **Later option, only if the above is too fiddly:** a paid-account native app (about 100 lines) via TestFlight. Not worth it for one household.

## Missing evidence
- Whether NFC.cool's "Write NFC" is free; whether it can return to Safari; the exact parameter UI of the intent. All need a real iPhone test.
- The NFC row tier in Apple's capability table.
- Simply NFC and other apps were not checked.

---

# 2. Holo Taco wishlist

## Findings

1. **Claim:** holotaco.com is Shopify (`Shopify.shop = "holo-taco.myshopify.com"`, Dawn 4.0.0 base theme "2.0 LIVE", theme id 123914092634) and the wishlist is **custom theme code plus an in-house backend**, not Swym, Growave, Wishlist King or similar. Homepage and wishlist page HTML contain no Swym, Growave or Wishlist King markers. They contain `base.app.wishList.loadWishlist(wishlistProductsId, customerId, shareId, apiKey)` and `<span wishlist-button data-product-id=... data-variant=...>`.
   **Sources:** homepage and `/pages/wishlist` HTML, theme asset [`base.bundle.min.js`](https://www.holotaco.com/cdn/shop/t/148/assets/base.bundle.min.js?v=114203282743476458101788988438). **Support:** direct evidence. **Confidence:** high.

2. **Claim:** From the bundle: the backend is `https://wishlist.holotaco.com/api/v1/wishlist` (staging `wishlist-staging.<domain>`). Add is `POST` and remove is `PATCH`, with JSON `{customerId, productId, code?}` and a request header `key: <api key>`. Reading a shared list is `GET .../api/v1/wishlist?id=<shareId>` with the same `key` header, and the response is `{products: [...]}`. Product ids are Shopify numeric product ids. `shareId` and `code` exist, so share codes are a real feature in the code. The wishlist page renders each product card by fetching `/products/<handle>?view=wishlist`, which means the page works from **handles**. When a user is logged in, the `key` and `customerId` appear to be injected into the page's `loadWishlist(...)` call (the logged-out page shows `''`, `''`, and a UUID-shaped key `a63c5118-...`). The localStorage key `wishlist` holds an array of product ids.
   **Sources:** same bundle. **Support:** direct for the code, inference for runtime behaviour (I did not call the API). **Confidence:** medium-high.
   *I did not call the wishlist API. Doing so with the key would be undocumented use of the shop's service, and the key is not meant for a third party.*

3. **Claim:** I found **no user-visible share link or export**. Holo Taco's FAQ describes adding via the sparkle icon and viewing under My Account → Wishlist, and does not mention sharing. A Reddit thread suggests the wishlist is account-based. The logged-out wishlist page has social "share" buttons only for products (Facebook, Twitter, Pinterest, email, copy link), not for the wishlist. The URL shape of a shared wishlist page (for example a `?code=` parameter on `/pages/wishlist`) is **not verifiable** without a logged-in session.
   **Sources:** [Holo Taco FAQ](https://www.holotaco.com/pages/faq) (via search summary), [Reddit r/theholotaco](https://www.reddit.com/r/theholotaco/comments/1fpj649) (could not fetch), wishlist page HTML. **Support:** absence of evidence. **Confidence:** medium-low.

4. **Claim:** The public Shopify `products.json` is not affected by wishlist state. A handle-to-shade mapping that polished already has from its catalog sync is enough to resolve what she saves.
   *Researcher inference.* **Confidence:** medium.

## Recommended import path (in order)
1. **Bookmarklet / paste snippet on her logged-in wishlist page** (most robust, no server-side scraping of holotaco.com, no credentials leave her browser). The page already renders product cards for her list, so the bookmarklet only reads anchors `a[href*="/products/"]` inside `.section-wishlist`, extracts handles (`/products/<handle>`), and sends `{handles:[...]}` to polished. On iOS Safari, bookmarklets are awkward. A better iPhone/Mac route is a **Shortcut with "Run JavaScript on Web Page"** in the Share sheet (Safari), which then does an HTTPS POST to polished, or "Copy to clipboard" followed by pasting into polished. Auth: send a short-lived one-time token in the URL that polished generated.
2. **Paste product links or text:** the app parses `/products/<handle>` from any pasted text (also handles the "Share → Copy" per-product links). Slow for a big wishlist but works with zero scripts.
3. **Share-code import:** only if she or Jan finds an actual share link in her account. Then the app could parse the code. Don't build before seeing a real link.

## What would be fragile
- Everything depends on theme markup (`.section-wishlist`, `/products/<handle>` anchors) and the lazy-loaded card rendering (`?view=wishlist` fetch per product). Wait for the `.wishlist-grid` to have `loaded`, and handle pagination (the code has `setupGrid(ids, page, perPage)`).
- The `key` header and API URL are internal and can change without notice. Don't call the API from the server.
- Handles can change if a product is renamed; match by handle, fall back by title.
- Don't hammer holotaco.com; keep to the bookmarklet reading what is already on screen.

## Missing evidence
- Real share URL format and whether a share page exists. Ask her to check her Wishlist page for a share button and send a sample link, or look at the page markup while logged in.
- The exact DOM selectors on the logged-in page.

---

# 3. Beautiful date input on iOS Safari

## Findings

1. **Claim:** On iOS 26 Safari an `<input type=date>` with `appearance:auto` is taller than expected because it uses `box-sizing: content-box`; setting `appearance:none` restores `border-box` and fixes the layout (merged fix in Actual Budget, 2025-11-14).
   **Sources:** [actualbudget/actual PR #6145](https://github.com/actualbudget/actual/pull/6145). **Support:** direct. **Confidence:** high.

2. **Claim:** With `appearance:none`, an **empty** date input collapses (WebKit bug 198959, still open); the workaround is a height on `::-webkit-date-and-time-value` (e.g. `min-height: 1.5em`). iOS UA CSS centers the value text, so set `text-align:left`. Also `display:block` causes odd vertical alignment/extra padding (WebKit 139848), so leave `display` alone.
   **Sources:** [WebKit bug 198959](https://bugs.webkit.org/show_bug.cgi?id=198959), [WebKit 139848](https://bugs.webkit.org/show_bug.cgi?id=139848) (via search summary), [Go Make Things, 2025-10-21](https://gomakethings.com/articles/fixing-temporal-input-styling-in-safari/). **Support:** direct. **Confidence:** high.

3. **Claim:** Safari's date inputs are `display:inline-flex`; in iOS 17 `width:100%` was ignored, fixed in iOS 18+. Safari's inner `::-webkit-datetime-edit*` parts have their own padding; zeroing it normalises heights. WebKit bug 301648 (Oct 2025) reports width 100% miscalculation with padding on iOS date/time inputs.
   **Sources:** [Go Make Things](https://gomakethings.com/articles/fixing-temporal-input-styling-in-safari/), [WebKit 301648](https://bugs.webkit.org/show_bug.cgi?id=301648). **Support:** direct. **Confidence:** high for the quoted behaviour, medium for exact iOS version boundaries (the author tested iOS 17 and 18, not 26).

4. **Claim:** `showPicker()` on date inputs is not available on iOS Safari (supported on desktop Safari), so a button that calls `input.showPicker()` will not work on iPhone. Use a real input covering the button.
   **Sources:** [web-features explorer: showPicker() for input](https://web-platform-dx.github.io/web-features-explorer/features/show-picker-input/), [MDN showPicker](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/showPicker) (via search summary). **Support:** direct. **Confidence:** medium (caniuse not re-verified for iOS 26).
   Do not use `display:none`, `visibility:hidden` or `disabled` on the native input.

## Snippets
These come from the cited sources, combined by me. **Not tested on devices.** Test on a real iPhone and iPad; I could only validate them against the sources.

**A. Overlay pattern (recommended): HTML**
```html
<div class="date-field">
  <span class="date-field__label" id="d-label">Purchase date</span>
  <div class="date-field__control">
    <span class="date-field__value" id="d-text" aria-hidden="true">Today, 26 Oct</span>
    <input type="date" id="d" name="purchased_on"
           value="2026-10-26" max="2026-10-26"
           aria-labelledby="d-label">
  </div>
  <div class="date-field__presets" role="group" aria-label="Quick dates">
    <button type="button" data-date="today">Today</button>
    <button type="button" data-date="yesterday">Yesterday</button>
  </div>
</div>
```
Server-render the initial text. A tiny ES module only does: on `change`/`input` of `#d`, format `input.valueAsDate` with `Intl.DateTimeFormat(undefined,{day:'numeric',month:'short'})` and write it into `#d-text`; the presets set `input.value` (in local time, not `toISOString()`, which gives UTC) and dispatch `change`.

**A. CSS**
```css
.date-field__control{position:relative;display:flex;align-items:center;
  min-height:44px;padding:0 14px;border:1px solid var(--line);
  border-radius:12px;background:var(--surface);}
.date-field__value{pointer-events:none;font:inherit;}
.date-field__control input[type="date"]{
  position:absolute;inset:0;width:100%;height:100%;
  opacity:0;               /* invisible but still tappable */
  font-size:16px;          /* prevents iOS focus zoom */
  -webkit-appearance:none;appearance:none;box-sizing:border-box;
  cursor:pointer;}
```
The visible text is `aria-hidden`; the real input keeps its accessible name through `aria-labelledby`, and it is the focus target. Show a focus ring on the wrapper with `.date-field__control:focus-within{outline:2px solid var(--focus)}`.

**B. Styling the native input directly (no overlay)**
```css
input[type="date"]{
  -webkit-appearance:none;appearance:none;box-sizing:border-box;
  min-height:44px;width:100%;padding:0 14px;font:inherit;}
input[type="date"]::-webkit-date-and-time-value{
  min-height:1.5em;text-align:left;}
::-webkit-datetime-edit,
::-webkit-datetime-edit-fields-wrapper,
::-webkit-datetime-edit-text,
::-webkit-datetime-edit-day-field,
::-webkit-datetime-edit-month-field,
::-webkit-datetime-edit-year-field{padding:0;}
```
Do not set `display:block`. Always give the input a `value` (default today) so the empty-height bug does not appear; the empty-value rules are only a safety net.

**Accessibility notes:** keep a visible `<label>`, keep the native input in the tab order, make presets real `<button type=button>` elements with 44px targets and a pressed state (`aria-pressed`) matching the selected date, and keep `max` set to today so the wheel cannot go to the future. Server must still validate `YYYY-MM-DD`.

## Contradictions
- None between sources on the main techniques. Version boundaries (iOS 17 vs 18 vs 26) come from different authors testing different versions; confirm on target devices.
- Web search summaries disagreed in detail on whether `-webkit-appearance:none` is required for the height fix; combining PR #6145 (iOS 26) and bug 198959 (older) suggests it is, for `border-box` reasons, but the overlay pattern avoids both.

## Missing evidence
- No real-device test of any snippet (none of this environment's tools can run iOS Safari).
- No test of iPadOS or macOS Safari rendering of the overlay.

## Sources
- Kept: [nfc.cool/developers](https://nfc.cool/developers/), [Apple URL scheme doc](https://support.apple.com/guide/shortcuts/run-a-shortcut-from-a-url-scheme-apd624386f42/ios), [Apple capabilities](https://developer.apple.com/help/account/reference/supported-capabilities-ios), [holotaco.com homepage / wishlist page / base.bundle.min.js](https://www.holotaco.com/cdn/shop/t/148/assets/base.bundle.min.js?v=114203282743476458101788988438), [WebKit 198959](https://bugs.webkit.org/show_bug.cgi?id=198959), [Go Make Things](https://gomakethings.com/articles/fixing-temporal-input-styling-in-safari/), [Actual PR 6145](https://github.com/actualbudget/actual/pull/6145).
- Deprioritized: search-engine summary answers (used only to find leads), App Store reviews, Reddit (could not fetch).

## Next steps
1. On an iPhone: install NFC.cool Tools, build the Shortcut, and check prefill, cost and return behaviour.
2. Ask her to open her logged-in wishlist page and check for a share button; capture the DOM or a sample link to settle the selectors.
3. Test the date snippets on iPhone, iPad and Mac Safari.
