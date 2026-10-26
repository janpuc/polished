# polished: visual design

The look of the app as built: the swatch book of the overhaul of 2026-10-25, lit and lettered by v3 run 1 of
2026-10-26 ("light and letters"). The direction is Fable's (`docs/advice/fable-swatch-book-2026-10-25.md`, then
`docs/advice/fable-v3-web-2026-10-26.md`, whose prototypes and screenshots are the visual target); this file
records what was built and where it departs (DESIGN.md section 14, items 41, 80 to 82 and 85). DESIGN.md wins
on behaviour; this file wins on looks. Everything lives in `static/css/app.css`. Runs 2 (three shells: side
nav, panel, per-shell sheets) and 3 (the Home shelf, wear) are not built; sections 5 and 6 say where they will
change this file.

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
  list row), `tip-l` 72 by 118 (the Home shelf, the Wheels list, the empty states' unpainted tip), `tip-xl` 96 by
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
`--slot-h` and `--rail`: 200px on Home (radius 78, tips 20 by 32), 72px in the Wheels list (radius 28, tips
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
colour change and no weight change; the title stays one inline run, so the mark never opens a gap.

**Home.** The greeting in Fraunces, "Good morning", "Good afternoon" or "Good evening" by the hour in
`POLISHED_TIMEZONE` and the first name of the signed-in account, with the date in `--ink-2` under it and the icon
tile (36px, radius 9, a `--mat` ring so plum does not vanish into plum) trailing on that row, a link to More; the
search field; the most recently touched wheel as a 200px ring with "Holos, 13 of 20 ›" under it (the whole block
is the link; with no wheel an unpainted ring and "No wheels yet, make one ›"); "Recent bottles" as a shelf of
`tip-l` with names under; one quiet line of links ("9 bottles, 8 shades, 6 wished"); a grouped list of Browse all
shades, Toppers, New and in stock, More. With no bottles the shelf is one line and one button, "Scan a bottle".
(The v3 shelf, the wear hero and the collection numbers are run 3.)

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

**Sheets** (`<dialog>`): opaque `--surface`, top radius 20, a 36 by 5 grabber, a title row with a text
"Cancel", a sticky footer with the translucent material and the one filled button, padding to the home
indicator. Secondary actions are quiet text at the foot (`.sheet-quiet`), red only where the action destroys.

**Empty states.** One line and one action; where a drawing helps it is the thing that will fill the space (the
unpainted ring on Home and in Wheels, the lit unpainted tip in a search with no result), never foil.

**Icons.** `static/icons/ui.svg`, 1.75px stroke at 24, `currentColor`, filled for the active tab. Added in
run 1: `calendar` (the date field), `qr`, `trash`, `sparkle`, `sidebar` and `arrow-up-right` (the last four wait
for runs 2 and 3). The level arc is CSS, not an icon.

## 7. The layer-stack builder

A sheet at `max-height: 92dvh`. Its head is the stack's composite tip (`tip-xl`, 96 by 158) beside "Slot 3", the
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
Under `prefers-reduced-motion` there is no scale, slide or turn; the sheet fades over 150ms and the save ring
shows still for a second. Transitions name their properties (never `all`). Nothing animates on load. The
authored arrival of a new bottle's tip, view transitions and the theme-switch suppression are run 3.

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
