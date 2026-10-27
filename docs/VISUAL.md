# polished: visual design

The look of the app as built: the swatch book of the overhaul of 2026-10-25, lit and lettered by v3 run 1 of
2026-10-26 ("light and letters"), given three shells by v3 run 2 of the same day (section 12) and a Home
shelf by v3 run 3 of 2026-10-27 (section 13). The direction is Fable's (`docs/advice/fable-swatch-book-2026-10-25.md`, then
`docs/advice/fable-v3-web-2026-10-26.md`, whose prototypes and screenshots are the visual target); this file
records what was built and where it departs (DESIGN.md section 14, items 41, 80 to 82 and 85 to 87). DESIGN.md wins
on behaviour; this file wins on looks. Everything lives in `static/css/app.css`.

## 1. Concept

**"The swatch book, lit."** A nail tech's colour chart: every shade in the app is a painted tip, laid on warm
paper at day and on the logo's dark plum at night. The chrome is ink and board only, so the colour comes from
the tips and nowhere else. Pink means one thing: wanted. The foil is for tips (the `?hl` ring, the save sweep,
the keyboard focus ring of a ring slot) and the logo only.

What makes it this app and not a Shopify companion: the content is drawn and lit. `tips.py` paints a nail from
a shade's colour and finish tags (DESIGN.md section 9); the page's CSS puts it under one light, top left, with
a contact shadow and a die-cut edge, so the tips read as painted nails on paper rather than decals. The same
drawing is the row's identity, the Home shelf, the shade head, the builder's head and the ring of the wheel.
Bottle photos are kept only where the bottle is the point: the strip on a shade page and the lookup result.

## 2. Tokens

Light and dark follow the system setting (`color-scheme: light dark`, two `theme-color` metas that follow
`--bg`). Hue 335; the light neutrals lean warm toward paper, the dark ones are unchanged from the first build.

| Role | Light | Dark |
|---|---|---|
| `--bg` the board | `#f7f3f2` | `#160b14` |
| `--surface` grouped lists, sheets, inputs | `#fefcfb` | `#20131d` |
| `--fill` controls at rest, empty tips | `#efe8e6` | `#30212c` |
| `--fill-2` pressed, selected track | `#e6dcd9` | `#3a2b36` |
| `--line` hairline | `#e3dad8` | `#372834` |
| `--line-2` input and chip border | `#c9bcb9` | `#4d3c49` |
| `--ink` | `#2a1623` | `#f7eff5` |
| `--ink-2` secondary text (6.2:1 and 8.1:1 on `--bg`) | `#6e5a63` | `#b7a4b2` |
| `--ink-3` icons and large text only | `#8f7d86` | `#92808d` |
| `--primary` / `--primary-on` | `#381531` / `#fff` | `#f7eff5` / `#280c23` |
| `--heart` | `#d83486` | `#ff77b4` |
| `--ok`, `--warn`, `--bad` | `#007840`, `#975800`, `#be222a` | `#61da92`, `#f9b64f`, `#ff7f7f` |
| `--velvet` the plate under the shade head | `--surface` | `#0f070e` |
| `--scrim-panel` the scrim behind the right-hand sheet | `rgb(42 22 35 / .25)` | `rgb(0 0 0 / .25)` |
| `--shadow-ink` (rgb channels of every shadow) | `40 20 30` | `0 0 0` |
| `--rim` the lit edge of a tip | `oklch(1 0 0 / .55)` | `oklch(1 0 0 / .26)` |
| `--mat` image outline | `oklch(0 0 0 / .1)` | `oklch(1 0 0 / .1)` |
| `--foil` | the conic gradient of the logo (unchanged) | same |

Rules:
- `--primary` is the cap of a Holo Taco bottle. **One filled action per view.** Selected (segment, level chip,
  active tab, a pressed preset) is the `--primary` fill with `--primary-on`, or ink with the filled icon for
  the tab. Links and text buttons are `--ink` at 600; nothing is coloured to say "tap me".
- Pink is the heart and the wishlist count, nothing else. `--bad` is a sold-out word, an error and a
  destructive action; `--warn` is retired or retiring. Status words are text colour only, never a fill.
- Foil only on tips: the `?hl` ring, the save sweep, the keyboard focus ring of a ring slot, the logo. Never on
  chrome or empties. Nothing is gradient text.
- No tinted notice box: a note is plain `--ink-2` text; an error is `--bad` text beside the field.
- No paper grain (invisible on retina at 3 percent, dirties the tips at 5).
- `prefers-contrast: more` darkens `--line`, `--line-2` and `--mat` and outlines groups.

## 3. Type

SF Pro (`system-ui`) for everything, and **Fraunces for four roles**. Dynamic Type, `tabular-nums` on prices,
counts and the hub, `text-wrap: balance` on titles and `pretty` on paragraphs.

**Fraunces** (SIL OFL 1.1) is vendored under `static/vendor/fraunces/`: the Fontsource variable file, instanced
to `wght` 500 to 700 and `opsz` 72 to 144 (no SOFT or WONK) and subset to Latin and Latin-ext with kerning,
ligatures and tabular figures kept (52 KB and 29 KB; the Latin file is preloaded, the Latin-ext one is fetched
by `unicode-range` only when a name needs it). `VERSIONS.txt` has the version, the tarball URL and the hashes;
the licence is `OFL.txt`. `font-display: swap` over a `Fraunces fallback` face, Georgia scaled to 77.4 percent
(measured against Fraunces 600 at opsz 144 over the greeting and some shade names) with Fraunces' own ascent
and descent, so the greeting does not jump when the font arrives. It is used at weight 600 with
`font-variation-settings: "opsz" 144` set outright, because Safari's automatic optical sizing would pick the
text cut at these sizes.

| Role | Size/leading | Where |
|---|---|---|
| Greeting | 34/36 | Home: "Good afternoon, Dev" with the date under it in SF |
| Shade title | 28/31 | the shade head on the plate |
| Wheel name | 34/36 on the wheel page, 22/24 in the Wheels list | |
| Hub number | 56/56, tabular | the ring's hub |

Never below 22px, never on a row, button, label, chip, tab, meta line, summary or sheet title (a test reads
`app.css` and fails if another selector takes the face). Everything else:

| Role | Size/leading | Weight | Tracking |
|---|---|---|---|
| Large title (page) | 34/41 | 700 | -0.02em |
| Sheet title | 28/34 | 700 | -0.02em |
| Section title | 22/28 | 600 | -0.01em |
| Row name, headline, buttons | 17/22 | 600 | 0 |
| Body | 17/22 | 400 | 0 |
| Subhead (finishes, status, a bottle's first line, a date's words) | 15/20 | 400 | 0 |
| Footnote (the P code, notes, "×2") | 13/18 | 400 | 0 |
| Caption (tab labels, layer labels) | 12/16 | 500 | 0 |

The greeting has the full width (the logo mark trails on the date's row), so "Good afternoon, Georgia" stays on
one line at 390. No eyebrow above a heading, no caps labels, no middle dots, no spaced dashes.

## 4. Space, radii, materials

Spacing 4, 8, 12, 16, 24, 32, 48; gutter 16 (`--gutter`); inside a group 8, between groups 24, between
sections 32 with 12 under the heading; row padding 12 by 16. Tap targets are 44pt (`--tap`); `.btn` is 50.

Radii (concentric): tips have their own shape (`--r-tip`, `50% 50% 38% 38% / 62% 62% 30% 30%`); inputs, the
date field, the search field, chips and the filter button 10; buttons 12; a group 16 with 3px padding and a 1px
transparent border so a row inside is 12; the shade plate 20; the viewfinder 16; the sheet's top 20; 999 only
for the segmented control, the badge and the grabber.

Materials: **chrome is frosted, content is not.** The tab bar, the stuck search bar and the sheet footer are
translucent (`--material`, `blur(20px) saturate(1.6)`, a 1px edge and a 1px inner top highlight,
`--material-light`: white at .35 in light and .08 in dark; opaque under `prefers-reduced-transparency`). A grouped
list is `--surface` with a 1px ring (`--ring-edge`; a transparent border under it keeps the edge in
forced-colors). No card shadows; tips are the exception (section 5). The two floating surfaces: the sheet
(`--sheet-shadow` over a scrim) and the filter panel (`--panel-shadow`: a soft drop in light, **only a 1px
ring in dark**, since a shadow on near-black is mud). Every content image has a 1px `--mat` outline.

## 5. Tips, the ring and the wheel

**The lit tip** (`_tip.html`, four sizes): `<span class="tip tip-m"><span class="tip-face"><img></span></span>`.
The painted SVG is the paper and the CSS is the light, because the light depends on the board, the scheme and
where it comes from; `tips.py` keeps the paint (base, finish, the gloss stripe, the small highlight at (66, 30),
the dome whose edge is .18).
- `.tip` holds the **contact shadow** (`::before`, a blurred ellipse under the foot in `--shadow-ink`) outside
  the clip, and sets the light direction (`--lx`, `--ly`, top left).
- `.tip-face` clips the picture to the tip shape and carries the **die-cut edge** (a 1.5px `--surface` ring in
  light, a 1px white .14 ring in dark), a 1px lift and a soft drop.
- `.tip-face::after` is the light on the surface, `soft-light`: a specular pool at the light's side, a diagonal
  gloss band, the 1px `--mat`, the `--rim` on the lit edges and an occlusion on the others.
- Sizes (tokens `--tip-*`): `tip-s` 28 by 46 (inline, the bought sheet, "Swatched on"), `tip-m` 40 by 66 (every
  list row), `tip-l` 72 by 118 (the Home rack, the Wheels list, the empty states' unpainted tip), `tip-xl` 96 by
  158 (the shade head, the builder's head). `tip-s` has no lift. The ring's slots are 38 by 62.
- A shade with no colour yet is drawn neutral; `unpainted()` is a lit tip with no painting, for a state that
  has no shade to show (no results).
- Black and near-black shades keep a silhouette in dark through the edge, the rim and the specular pool, not
  through a lighter fill.

**The shade head** is the tip at `tip-xl` beside the title (Fraunces 28), on a plate: `--surface` in light,
`--velvet` in dark so holo and glitter have something to stand out from. The strip of photos runs above it.

**The ring** (`.ring`, `wheel.html`): `min(100%, 390px)` square, radius 150px (it gives way to the gutter
under 400pt), tips 38 by 62 turned to their angle with slot 1 at twelve o'clock, a 1.5px `--line-2` hairline
circle 22px inside the radius that the tips sit on like the plastic ring of a real wheel. A filled slot is lit
like every tip, with the light turned back against the slot's angle (`--c`, `--s`, `--lx`, `--ly`) so it comes
from the top left on every tip and the shadow falls down the page. An empty slot is a `--fill` tip with its
number and no foil; a filled one is the stack's composite tip; a draft shows an ink dot at the stem; `?hl` puts
the foil ring on matching tips and dims the rest to 55 percent. The hub holds the count only, in Fraunces at 56,
with "of 20" as a footnote under it. Tapping a tip lifts it (`scale 1.08`) before the sheet rises; keyboard focus
shows the foil ring and an ink outline. The ring's spoken label (`#ring-label`, "Holos, 3 of 20 swatched") is
its own element, swapped out of band with the hub after a save, a clear or a rename.
Below the ring: "Swatches", a grouped list of the filled slots (number, composite tip at `tip-m`, summary,
date only when it differs from the row above), and a quiet row at the foot: Tag and QR code, Rename, Archive,
Delete wheel.

**The ring at small sizes** (`_mini_ring.html`) is the same markup and CSS with other values of `--ring`,
`--slot-h` and `--rail`: 132px in Home's wheel card (radius 51, tips 13 by 21), 200px on the Wheels page when
there is no wheel yet (radius 78, tips 20 by 32), 72px in the Wheels list (radius 28, tips
9 by 14). Tips only, not tappable, never wider than their pitch; they keep the edge and a contact shadow but
no pool or rim, which a tip that small cannot carry.

## 6. Components

**Buttons.** Primary: `--primary` fill, 50pt, radius 12, 17/600, one per view. Secondary: `--fill`, ink text.
Text: ink 600 on nothing, a `--fill` wash while pressed. Icon buttons are 44 by 44 with an `aria-label`. The
heart on a shade page is an icon button beside "Add bottle": ink on `--fill`, `--heart` when wished.
Press scales to .96 (150ms, `:not(:disabled)`); hover colours only under `@media (hover: hover)`.

**Inputs and chips.** `--surface` with a `--line-2` border and radius 10; focus is a 2px ink outline. Chips
(`.pick` checkboxes, `a.chip`, the date presets) are outlined, 44pt tall, radius 10; selected is `--primary`
with `--primary-on`. The segmented control is the one pill: a `--fill` track, the selected segment `--primary`.
The search field is `--fill` with the camera button inside it; it is sticky and turns to material when stuck.

**The date field** (`_date_field.html`, `static/js/date.js`; every date input in the app). A field styled like
every input (50pt, radius 10, `--line-2`): a calendar icon, the value in words (**"Today"** 26 Oct 2026,
**"Yesterday"**, "21 Jul 2026" and the weekday in `--ink-2`, or "Not yet" or the field's own empty word in
`--ink-3`), a chevron. Under it the presets as chips: Today, Yesterday and, on an optional field only, the
empty word ("Don’t know" for Bought on, "Not opened" for Opened on); the one that matches is pressed. The real
`<input type="date">` covers the field with `opacity: 0`, 16px text and `max` = today, so a tap opens the native
picker (the wheel on iPhone and iPad, the popover on a Mac) and the keyboard and a screen reader meet a plain
date input; focus shows the ink outline on the whole box (`:has(:focus-visible)`). The words and the pressed
preset follow the input's value (`date.js`, delegated from the document, days as UTC midnights so the browser's
time zone never moves one). The server checks every date too: after today is refused with "That date is in the
future".

**The bottle level** is an arc in ink, never in the shade's colour (a dark shade's colour vanishes on the dark
board): `.level` is `<i class="level-arc">` (20px, a conic fill clockwise from twelve over a `--line-2` track,
masked to a ring) and the word. The share is a class (`level-full` 100, `-half` 50, `-low` 25, `-empty` 0)
because the CSP forbids inline style. **Low** and **Empty** keep their word colour (`--warn`, `--bad`) so colour
is never the only carrier. In the edit sheet each segment of the Level control shows the same arc at 16px, and
the selected segment draws it in `--primary-on`.

**Rows.** A shade row is the tip at `tip-m`, then a grid: the name (17/600, one line, ellipsis) with a pink
heart right after it when wished, the price at the trailing edge, and under them the status word (`--bad` or
`--warn`, 600) with the finishes in `--ink-2`, and "×N" as a footnote under the price when owned. Hairlines
start under the title, not under the tip. **Bottle rows** (`_bottle_card.html`) are plain rows of a group, a
grid of `1fr auto auto`: the first line is the purchase ("Bought 21 Jul 2026, $15.50", 15/400 ink), then "Opened
5 Oct 2026" and the notes; the **P code is the last and lightest fact**, a trailing 13/400 `--ink-3` figure after
an 8px gap on the first line (no separator, and left out when the bottle has none); then the level arc and its
word in a column as wide as "Empty", so the arcs line up down the list, then a chevron. The row opens the edit
sheet, whose order is Level, Bought on, then "More details": Price paid, Opened on, P code, Notes. Wishlist
rows, slot rows and the Wheels list follow the same grid: tip or ring, name, trailing facts.

**Search marks.** The letters of a result that hit are wrapped in `<mark>`: a 12 percent ink wash, radius 3, no
colour change and no weight change; the title stays one inline run, so the mark never opens a gap. When typo
tolerance found some of the matches the count line reads "3 matches, closest first". Names that are all but
the same as another row of the page carry the official collection (else the release year) in `--ink-3` at 13px
after the finishes. The first result is the cursor (`aria-current`, a `--fill` row) that Enter opens.

**Home** is the shelf of section 13: the greeting, the search, Wear today, the Recently added rack on its ledge, the
wheel card, the collection numbers and three links.

**Shades.** Title with a "+" , the search field and a filter button with a count badge, "372 shades", then
rows. With no match: the unpainted tip, "No shades match", "Nothing matches “overstim”. Try fewer letters, or clear
a filter." and "Add by hand". The filter panel is a sheet-like drop-down: segmented controls for Kind, Status and
Mine, outlined chips for Finish and Colour, two selects, and a sticky bar with "Clear all" and the one filled
"Show N shades".

**Shade detail.** The strip of the brand's photos runs edge to edge (3:4, 70vw, radius 16, snap). Under it the
plate with the `tip-xl` beside the title, and on the line under the title the price, "Owned ×2" in ink 600 and
the status word. "Add bottle" is the one filled action, the heart sits beside it. Then "Bottles" (a group), a
quiet list of Finish, Colour and Collections (a 13px label over outlined chips), "Swatched on" rows led by the
stack's tip, a closed "Tip colour" disclosure, and the store link and SKU as footnotes. A shade with a release
date adds a footnote under that line, "Released 6 Jul 2019" in `--ink-2`, and its official collection is the first
chip of Collections (`.chip-long`: it wraps instead of running off the screen, since a name can be 51
characters). A shade only the release sheet lists has no strip and no price: the tip is the hero, "Not in the
shop" is a quiet `--ink-2` word in the subhead (and in rows, where the price would be), and the store link and
SKU are absent.

**Lookup.** The camera is first: a 4:3 viewfinder (radius 16) with a "Scan the barcode" button on an idle tile
until the camera runs, a caption "Point at the barcode under the bottle", one field "Type the digits, a P code,
or a name", "Take a photo instead" as a text action, the result, and a "Learned codes" row. A result is a
group with the bottle photo (72 by 96) beside the shade's own `tip-l`, then the name, finishes and price.

**Sheets** (`<dialog>`): opaque `--surface`, top radius 20, a 36 by 5 grabber (a drag handle on the phone,
section 12), a title row with a text "Cancel", a sticky footer with the translucent material and the one filled
button, padding to the home indicator. Secondary actions are quiet text at the foot (`.sheet-quiet`: Archive
this bottle, Archive wheel in the Rename sheet), red only where the action destroys. The shape changes by
shell (section 12).

**Delete wheel** is a sheet: "Delete Holos?", "This removes the wheel, its 14 swatches and its tag address. The
sticker will stop opening anything.", the wheel's mini ring (72px) with "Holos, 14 of 20", and the one filled
button in `--bad`. The wheel page's foot is three quiet words, Tag and QR code, Rename and Delete (the last in
`--bad`).

**The tag page.** Title, a lede, the QR at 216px on a 12px white plate (radius 16), the address field, **Copy
address** (the filled action; "Open the wheel" is secondary), then "Write the tag" with the four NFC Tools
steps, then "Move the tag" and the quiet red "New tag URL". From 700px the lede reads "Scan this with the iPhone
camera, then write the sticker from NFC Tools there. Or write it from the Polished app on iPhone." and the
steps sit in a closed disclosure.

**Empty states.** One line and one action; where a drawing helps it is the thing that will fill the space (the
unpainted ring on Home and in Wheels, the lit unpainted tip in a search with no result), never foil.

**Icons.** `static/icons/ui.svg`, 1.75px stroke at 24, `currentColor`, filled for the active tab. Added in
run 1: `calendar` (the date field), `qr`, `trash`, `sparkle`, `sidebar` and `arrow-up-right` (the last four are still unused). Run 2 added `ellipsis` (More in the side nav). The level arc is CSS, not an icon.

## 7. The layer-stack builder

A sheet at `max-height: 92dvh` (a right-hand panel on the panel shell, section 12). Its head is the stack's composite tip (`tip-xl`, 96 by 158) beside "Slot 3", the
wheel name as a caption and Cancel, with the summary under them as body text; every layer edit appends the new
composite over the old one and fades it in once loaded. Layers are a list on a 2px rail through their
tips: label (Base, 2nd, Top), name, an iOS-style hairline stepper for coats, move arrows from three layers on,
remove. Shortcuts (Over black, Copy from…, Same as last) are outlined chips that wrap. Then the search field
with the camera button, an Owned / Toppers / All segmented control, result rows with a trailing "+", a
disclosure for name, note and "Swatched on" (a date field), and the sticky "Save swatch".

## 8. Motion

Four moments, on `transform`, `scale` and `opacity`:
- Sheet: `translateY(100%)` to 0 over 380ms `cubic-bezier(.22,.9,.32,1)`, back over 240ms with
  `cubic-bezier(.68,0,.78,.1)`, the scrim fading with it (`@starting-style`, `allow-discrete`).
- Press: `scale(.96)` over 150ms ease-out; rows wash to `--fill` at once.
- A ring tip lifts to 1.08 before the sheet rises; a saved slot gets one foil sweep (700ms).
- A new builder tip fades in over the old one; the "+" of the Wheels list turns to ×.
The wider shells add: the centred modal arrives from `scale .96` and `opacity 0` over 240ms and leaves over
240ms; the right-hand sheet slides in over 280ms and out over 200ms; the shade panel slides over 280ms and 200ms.
Under `prefers-reduced-motion` there is no scale, slide or turn; the sheet and the panel fade over 150ms and the
save ring shows still for a second. Transitions name their properties (never `all`). Nothing animates on load. The
arrival of a new bottle's tip, the row to shade view transition and the theme-switch suppression are run 3
(section 13.4).

## 9. Copy

Sentence case everywhere. Buttons name the result and keep their name ("Add bottle", "Save swatch"). Errors
say what and how ("Coats must be 1 to 5.", "That date is in the future. Pick today or an earlier day."). Empty
states are one line and one verb. Counts are plain ("13 of 20, 2 drafts", "9 bottles"). Section headings are
nouns she would say: Bottles, Swatches, Swatched on. "Wished" and "Owned ×2" are the two words for what she has
and wants.

## 10. Checklist (390 by 844 and 1440 by 900, light and dark)

Every tip has a contact shadow and an edge, in rows, the ring, the shade head, the builder and the empty states.
A black shade keeps a silhouette in dark. The greeting is Fraunces on one line at 390 for a seven-letter name;
no serif glyph is smaller than 22px or sits on a row, button, label, chip, tab, meta line or summary; no
gradient text. The level arc is ink in both modes and the Low and Empty words are coloured. The P code is the
last and lightest fact of a bottle row. A date field shows words and the native input behind it takes focus and
opens the picker; a date after today is not accepted. A search marks the letters that hit and the no-results
state shows the unpainted tip. No lilac or pink fill anywhere except the heart. One filled button per screen.
The font is served from `/static/vendor/`, no request leaves the server except Shopify's image CDN. The Shades
list at 372 rows scrolls without jank on the iPhone profile. The sheet clears the home indicator, the tab bar's
active tab is ink, nested radii are concentric (16, 3 padding, 12), dark surfaces carry the ring, not a
shadow, the reduced-motion run shows no sliding, the largest Dynamic Type size does not clip a row name. No
console error.

## 11. Logo

Revised the same day after the first build read as a jelly bean at 180px: a bare capsule with a
semicircle cap has no nail cues. The mark is now **a nail painted in holographic foil, overhanging a
stylised fingertip, on plum**. The source of truth is `src/polished/static/icons/logo.svg` and
`favicon.svg`; `scripts/make_icons.py` rasterises them.

- Ground: full-bleed square, radial `#3a1c45` to `#180b1e`. No rounding (iOS masks it).
- Finger: a plum-mauve silhouette (`#86537f` to `#2a1532`, top to bottom), not a skin tone, rising
  from the bottom edge to an apex at y 30. The nail's free edge overhangs it by 8 units, which is
  the strongest single "nail" cue.
- Nail: a squoval (flatter cubic cap, not a semicircle), 36 wide, y 22 to 70, drawn three times:
  seven-stop saturated foil over the whole hue circle, a perpendicular white sheen, and a dark rim
  "dome" so it curves.
- Nail cues: lunula at 30 percent white, a lighter free-edge band above a 1.6-unit smile line,
  a soft radial gloss, and one four-point sparkle at the upper right.
- Favicon (also the header mark): the foil nail enlarged on a rounded plum tile, the free-edge band
  as a fill (strokes vanish at 16px), no gloss, lunula or finger.
- Maskable 512: every meaningful part is inside the 80 percent safe circle (farthest point, the
  sparkle tip, is 37.7 units from the centre); the finger bleeds off the bottom by design.
- No filters, no `<style>`, path data repeated instead of `<use>` so every rasteriser agrees.

## 12. Three shells

One HTML, three layouts chosen by viewport width (never by user agent): **phone** under 700px, **rail** from
700 and **panel** from 1000 (**sidebar** from 1280 within it). Everything is the final block of `app.css`
("17. Three shells") and overrides the phone rules above it.

| | Phone, under 700 | Rail, 700 to 999 | Panel, 1000 and up (sidebar from 1280) |
|---|---|---|---|
| Navigation | frosted tab bar | 72px icon rail, tooltips under a pointer | the rail; from 1280 a 240px sidebar with words, `/` on Shades, More and "Signed in as" at the foot |
| Page | 40rem column, gutter 16 | gutter 24; lists and grids use the width | gutter 24 (32 from 1280); `main.wide` is 1120px |
| `#sheet` | bottom sheet, grabber drags it down | centred modal, max 560, radius 20, no grabber | right-anchored panel, 360 (400 from 1280), full height, sticky frosted head and footer |
| Shade | a page | a page | `#panel` beside the list, 360 (400), non-modal |
| Tips | `tip-m` 40 by 66, `-l` 72 by 118, `-xl` 96 by 158 | `-m` 44 by 72, `-l` 88 by 144, `-xl` 120 by 197 | as rail, `-l` 96 by 158 from 1280; `-xl` back to 96 by 158 in the panel and the sheet |

The side nav is `--bg` mixed 30 percent toward `--fill` with a 1px `--line` on its trailing edge; the active link is a
`--fill` row with the filled icon (as the tab bar's active tab). Labels are visually hidden on the rail and become
tooltips (`data-tip`) on hover and keyboard focus; from 1280 they are shown. A modal sheet pads the page behind it
(`padding-right`) so the wheel's ring stays beside the builder instead of under it.

**The shade panel** is `position: fixed` on the right, `--surface` with a 1px `--line` on its leading edge, a
frosted sticky bar ("Shade", and a 32px round close button with a 44px hit area) and the shade page's own content
under it (two photos across, the head on its plate, Add bottle, Bottles, the facets). The selected row is `--fill`
without its hairline. The panel is `inert` while closed.

**The Shades list** keeps its row; at the foot, once a keyboard has focused something, a floating hint line
(a frosted pill: "↑↓ move, Enter open, Esc close panel, / search, n add bottle" with `kbd` caps).

**Grids.** Wheels: two columns from 700, three from 1000, each wheel its own bordered card. Bottles: two columns
of shade groups from 900. History: a year's months in two columns from 1000. Wishlist: the checkout column is
stuck at 23rem with the wished shades beside it from 1000. Status pages (offline, signed out, sign-in refused)
are centred at 420px with no side nav.

**Checklist** (390, 834, 1024 and 1440, light and dark): at 834 the rail shows and the tab bar does not; at 1024 and
1440 a row click opens the panel without a page load, the URL updates, Esc closes it, Back closes it; the builder
is a right panel at 1440 with its footer stuck; at 390 nothing changed but the grabber drags; `/` focuses search;
Delete asks, deletes and lands on Wheels with "Deleted Holos"; the tag page shows the steps on the phone and the
collapsed version with the iPhone lede on the rail and panel shells.

## 13. Home, the shelf

Run 3. A shelf, not a dashboard: one column on the phone, two from 700 (`.home-cols`; the main column is
`main.wide`). Every part is a section with its own heading (`aria-labelledby`); "Wear today", "Recently added",
"Wheels" and "Collection" are section titles (22/28, 600), never eyebrows. A section's trailing link ("All 9
bottles", "All 2") is 15/600 `--ink-2` with a 44px hit area.

| | Phone, under 700 | Rail, 700 to 999 | Panel, 1000 and up |
|---|---|---|---|
| Order | greeting, search, Wear today, rack, wheel, collection, links | the hero and the rack left; the wheel, the collection and the links in a 300px column right | as the rail, the right column 320px; 1120 wide, the sidebar from 1280 |
| Rack pitch | 88px, a tip peeks at the edge | 104px | 104px, 120px from 1280 |
| Greeting | 34/36 | 34/36 | 34/36, 40/42 from 1280 |

Home is about 1430px tall on the phone with nine bottles (the spec's limit is two screens, 1688).

**13.1 Wear today.** `#wear-slot` holds the hero (`_wear_hero.html`), the one block htmx swaps. The hero is a plate
(`--velvet`: the surface by day, the darkest plum by night, so holo and glitter have contrast) with the shade's
`tip-xl`, its name in Fraunces 28/31 (a link to the shade), one line of facts in `--ink-2` ("Holographic,
metallic, shimmer. P12, half left": the finishes, then the code and the level of the bottle that would be
worn) and two buttons. **I wore this** is the one filled action of Home (`POST /wear/{id}`); after it the same
place says "Worn today" with a check, nothing to press, and **Another** (secondary, `GET /wear/another?shown=`)
stays. On the phone the tip and the name sit side by side and the buttons span under them; once the slot is
440px wide (a container query, so the shell decides through the column) the buttons move beside the tip. The
two buttons carry ids (`wear-primary`, `wear-another`) so htmx gives focus back to the same place after a swap.
With nothing owned the hero is the unpainted tip, "Nothing to wear yet" and "Scan a bottle" (the filled action
then). The hero's name link has 44px to hit by padding, not size.

**13.2 The rack.** `.rack` is a horizontal list of `tip-l` with the shade's name under (13/600, two lines
balanced), `scroll-snap-type: x mandatory`, snapping to the start. It stands on a **ledge**: a 1.5px `--line` rule
across the full width of the column (edge to edge on the phone) at the tips' foot, with a 10px gradient of
`--shadow-ink` at 8 percent (30 percent black in dark) under it. The ledge belongs to `.rack`, not to the
scrolling list, so it stays still while the tips pass over it; the contact shadows of the tips rest on it
(`.rack .tip::before { bottom: -7px; height: 10px }`) and a tip on the ledge has the die-cut edge and no lift.
The names sit under the ledge, with a zero-width break after a full stop so "Overstimulated.exe" breaks at the dot.
Six tips, newest first; "All 9 bottles" (or "1 bottle"). An empty rack is three unpainted tips on the same ledge
and one line, "Bottles you add stand here, newest first." (no second button: the hero's is the one).

**13.3 Wheel card and collection.** The wheel card is a `--r-group` card with a 132px ring (tips only, no
chevron: the whole card is the link), the wheel's name in Fraunces 22/24 and "14 of 20, 1 draft" in `--ink-2`;
"All 2" only with more than one wheel. With no wheel: the unpainted ring (12 tips), "No wheels yet" in the sans
face (it is a sentence, not a wheel's name) and "Make one". **Collection** is a group of three links (bottles,
shades, wished and what it comes to), each number in Fraunces 28/28, tabular; the wished number is `--heart`
(pink means wanted), the others ink. It is hidden while all three are zero. Below, the group of three links:
Browse all shades, Toppers, New and in stock. More is the mark beside the greeting and the navigation.

**13.4 Motion.** Two authored moments and nothing on load.
- **A new bottle arrives**, once. The tip scales from .85 and fades in over 600ms on `linear(0, .4 7%, .8 15%,
  1.04 30%, .98 45%, 1)` while one specular sweep crosses it (`.tip-face::before`, a 115deg band whose
  background-position runs from -56 to 144 percent of the tip over 700ms, started 100ms in). It plays on the
  rack's first tip the next time Home is drawn after a bottle is added from a shade page (a one-use cookie,
  `polished_arrived`, read and cleared by Home so a reload does not replay it) and in place on the lookup's "Added"
  result.
- **Another** gives the hero's new tip the sweep alone.
- **Row to shade** is `@view-transition { navigation: auto }` with the shade's tip carried from the row or the rack
  to the head of the shade page (350ms, `cubic-bezier(.16, 1, .3, 1)`); the rest of the page cuts as before. The
  name `tip-{id}` is set by `transitions.js` (a classic script in the head, because `pagereveal` fires before a
  deferred script runs) only on that pair, through the style object since the CSP forbids a style attribute.
  Safari 18.2 and Chrome; a plain navigation elsewhere and on the panel shell, where a row opens in the panel.
- **Reduced motion:** the arrival is a 150ms fade (`tip-fade`), the hero after Another fades the same way, there is
  no sweep, no scale and no view transition (the at-rule lives inside `prefers-reduced-motion: no-preference`).
- **Theme switch:** when the system changes between light and dark `chrome.js` adds `theme-switching` to the root
  for two frames, which sets every transition to none, so no surface smears from one scheme to the other.

**13.5 Empty states** (one line and one action, drawn with the unpainted tip, never foil): the hero with no bottles,
the rack, the wheel card with no wheel, the Wishlist (`unpainted("l")` replaces the line drawing there), and the
search with no result (run 1).

**Checklist** (390, 834, 1024 and 1440, light and dark): Home fits two phone screens with nine bottles; the hero
plate is `--velvet` in dark; "I wore this" turns the hero to "Worn today" without a page load and a reload says the
same; Another shows a different shade with a sweep; a bottle added from its shade page arrives on the rack once
and a reload leaves it standing; the ledge runs the column's full width, its rule at the tips' foot and the
shadows on it; the 1440 Home has two columns with the rack under the hero; the reduced-motion run shows no sweep,
no scale and no view transition; the greeting, the hero's shade, the wheel's name and the three numbers are in
Fraunces and nothing under 22px is; one filled button; no horizontal overflow; no console error.
