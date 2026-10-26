# polished: visual design

The look of the app as built, from the overhaul of 2026-10-25 (runs 1, 2a and 2b). It replaces the first
VISUAL.md ("a pearl gallery", Fraunces, raspberry accent, bottle photos in every row). The direction is
Fable's (`docs/advice/fable-swatch-book-2026-10-25.md`, with the critique that led to it); this file records
what was built and where it departs from that report (DESIGN.md section 14, items 41 and 81 to 82).
DESIGN.md wins on behaviour; this file wins on looks. Everything lives in `static/css/app.css`.

## 1. Concept

**"The swatch book."** A nail tech's colour chart: every shade in the app is a painted tip, laid on a quiet
matte board, the logo's dark plum at night. The chrome is ink and board only, so the colour comes from the
tips and nowhere else. Pink means one thing: wanted. The foil is for tips and the logo only.

What makes it this app and not a Shopify companion: the content is drawn. `tips.py` paints a nail from a
shade's colour and finish tags (DESIGN.md section 9); the same drawing is the row's identity, the Home shelf,
the builder's head and the ring of the wheel. Bottle photos are kept only where the bottle is the point: the
strip on a shade page and the lookup result.

## 2. Tokens

Light and dark follow the system setting (`color-scheme: light dark`, two `theme-color` metas). Hue 335.

| Role | Light | Dark |
|---|---|---|
| `--bg` the board | `#f6f2f5` | `#160b14` |
| `--surface` grouped lists, sheets, inputs | `#fdfbfc` | `#20131d` |
| `--fill` controls at rest, empty tips | `#ece5ea` | `#30212c` |
| `--fill-2` pressed, selected track | `#e3dbe1` | `#3a2b36` |
| `--line` hairline | `#ddd5db` | `#372834` |
| `--line-2` input and chip border | `#c5bac2` | `#4d3c49` |
| `--ink` | `#261322` | `#f7eff5` |
| `--ink-2` secondary text (6.0:1 and 8.2:1) | `#6b5666` | `#b7a4b2` |
| `--ink-3` icons and large text only | `#8c7a87` | `#92808d` |
| `--primary` / `--primary-on` | `#381531` / `#fff` | `#f7eff5` / `#280c23` |
| `--heart` | `#d83486` | `#ff77b4` |
| `--ok`, `--warn`, `--bad` | `#007840`, `#975800`, `#be222a` | `#61da92`, `#f9b64f`, `#ff7f7f` |
| `--mat` image outline | `oklch(0 0 0 / .1)` | `oklch(1 0 0 / .1)` |
| `--foil` | the conic gradient of the logo (unchanged) | same |

Rules:
- `--primary` is the cap of a Holo Taco bottle. **One filled action per view.** Selected (segment, level chip,
  active tab) is the `--primary` fill with `--primary-on`, or ink with the filled icon for the tab. Links and
  text buttons are `--ink` at 600; nothing is coloured to say "tap me".
- Pink is the heart and the wishlist count, nothing else. `--bad` is a sold-out word, an error and a
  destructive action; `--warn` is retired or retiring. Status words are text colour only, never a fill.
- Foil only on tips: the `?hl` ring, the save sweep, the logo. Never on chrome or empties.
- No tinted notice box: a note is plain `--ink-2` text; an error is `--bad` text beside the field.
- `prefers-contrast: more` darkens `--line`, `--line-2` and `--mat` and outlines groups.

## 3. Type

SF Pro only (`system-ui`), no webfont (nothing to download, Dynamic Type and optical sizes for free).
`font-optical-sizing: auto`, `tabular-nums` on prices, counts and the hub, `text-wrap: balance` on titles
and `pretty` on paragraphs. The display moment belongs to the tips, not to letterforms.

| Role | Size/leading | Weight | Tracking |
|---|---|---|---|
| Large title (page, Home) | 34/41 | 700 | -0.02em |
| Shade title (detail), sheet title | 28/34 | 700 | -0.02em |
| Section title | 22/28 | 600 | -0.01em |
| Row name, headline, buttons | 17/22 | 600 | 0 |
| Body | 17/22 | 400 | 0 |
| Subhead (finishes, status, price in the meta line) | 15/20 | 400 | 0 |
| Footnote (dates, notes, "×2") | 13/18 | 400 | 0 |
| Caption (tab labels, layer labels) | 12/16 | 500 | 0 |
| Hub number | 44/48 | 700, tabular | -0.03em |

No eyebrow above a heading, no caps labels, no middle dots, no spaced dashes.

## 4. Space, radii, materials

Spacing 4, 8, 12, 16, 24, 32, 48; gutter 16 (`--gutter`); inside a group 8, between groups 24, between
sections 32 with 12 under the heading; row padding 12 by 16. Tap targets are 44pt (`--tap`); `.btn` is 50.

Radii (concentric): tips have their own shape (`--r-tip`, `50% 50% 38% 38% / 62% 62% 30% 30%`); inputs, the
search field, chips and the filter button 10; buttons 12; a group 16 with 3px padding and a 1px transparent
border so a row inside is 12; the viewfinder 16; the sheet's top 20; 999 only for the segmented control, the
badge and the grabber.

Materials: the tab bar, the stuck search bar and the sheet footer are translucent (`--material`,
`blur(20px) saturate(1.6)`, a 1px edge; solid under `prefers-reduced-transparency`). A grouped list is
`--surface` with a 1px ring (`--ring-edge`, black at .06 in light, white at .08 in dark; a transparent
border under it keeps the edge in forced-colors). No card shadows. The two floating surfaces: the sheet
(`--sheet-shadow` over a scrim) and the filter panel (`--panel-shadow`: a soft drop in light, **only a 1px
ring in dark**, since a shadow on near-black is mud). Every content image has a 1px `--mat` outline inset by
1px.

## 5. Tips, the ring and the wheel

**Tips** (`_tip.html`, four sizes): `tip-s` 28 by 46 (inline, the bought sheet, Swatched on), `tip-m` 40 by
66 (every list row), `tip-l` 56 by 92 (the Home shelf, the shade page), `tip-xl` 72 by 118 (the builder's
head). Each is the painted SVG clipped to the tip shape, with a 1px `--mat` inset, a soft gloss from the top
left and a 1px highlight at the bottom right. A shade with no colour yet is drawn neutral.

**The ring** (`.ring`, `wheel.html`): `min(100%, 390px)` square, radius 150px (it gives way to the gutter
under 400pt), tips 38 by 62 turned to their angle with slot 1 at twelve o'clock, a 1.5px `--line-2` hairline
circle 22px inside the radius that the tips sit on like the plastic ring of a real wheel. An empty slot is a
`--fill` tip with its number and no foil; a filled one is the stack's composite tip; a draft shows an ink dot
at the stem; `?hl` puts the foil ring on matching tips and dims the rest to 55 percent. The hub holds the
count only, with "of 20" as a footnote under it. Tapping a tip lifts it (`scale 1.08`) before the sheet rises.
Below the ring: "Swatches", a grouped list of the filled slots (number, composite tip at `tip-m`, summary,
date only when it differs from the row above), and a quiet row at the foot: Tag and QR code, Rename, Archive.

**The ring at small sizes** (`_mini_ring.html`) is the same markup and CSS with other values of `--ring`,
`--slot-h` and `--rail`: 200px on Home (radius 78, tips 20 by 32), 72px in the Wheels list (radius 28, tips
9 by 14). Tips only, not tappable, never wider than their pitch.

## 6. Components

**Buttons.** Primary: `--primary` fill, 50pt, radius 12, 17/600, one per view. Secondary: `--fill`, ink text.
Text: ink 600 on nothing, a `--fill` wash while pressed. Icon buttons are 44 by 44 with an `aria-label`. The
heart on a shade page is an icon button beside "Add bottle": ink on `--fill`, `--heart` when wished.
Press scales to .96 (150ms, `:not(:disabled)`); hover colours only under `@media (hover: hover)`.

**Inputs and chips.** `--surface` with a `--line-2` border and radius 10; focus is a 2px ink outline. Chips
(`.pick` checkboxes, `a.chip`) are outlined, 44pt tall, radius 10; selected is `--primary` with
`--primary-on`. The segmented control is the one pill: a `--fill` track, the selected segment `--primary`.
The search field is `--fill` with the camera button inside it; it is sticky and turns to material when stuck.

**Rows.** A shade row is the tip at `tip-m`, then a grid: the name (17/600, one line, ellipsis) with a pink
heart right after it when wished, the price at the trailing edge, and under them the status word (`--bad` or
`--warn`, 600) with the finishes in `--ink-2`, and "×N" as a footnote under the price when owned. Hairlines
start under the title, not under the tip. Bottle rows (`_bottle_card.html`) are plain rows of a group: P
code, a footnote of when and how much, and a level glyph (a small bottle filled to the level in the shade's
own colour) with its word, then a chevron; the row opens the edit sheet. Wishlist rows, slot rows and the
Wheels list follow the same grid: tip or ring, name, trailing facts.

**Home.** The icon tile (36px, radius 9, a `--mat` ring so plum does not vanish into plum) and "Polished" as
the large title; the search field; the most recently touched wheel as a 200px ring with "Holos, 13 of 20 ›"
under it (the whole block is the link; with no wheel an unpainted ring and "No wheels yet, make one ›");
"Recent bottles" as a shelf of `tip-l` with names under; one quiet line of links ("9 bottles, 8 shades, 6
wished"); a grouped list of Browse all shades, Toppers, New and in stock, More. With no bottles the shelf is
one line and one button, "Scan a bottle".

**Shades.** Title with a "+" , the search field and a filter button with a count badge, "372 shades", then
rows. The filter panel is a sheet-like drop-down: segmented controls for Kind, Status and Mine, outlined
chips for Finish and Colour, two selects, and a sticky bar with "Clear all" and the one filled "Show N
shades".

**Shade detail.** The strip of the brand's photos runs edge to edge (3:4, 70vw, radius 16, snap). Under it
`tip-l` beside the title, and on the line under the title the price, "Owned ×2" in ink 600 and the status
word. "Add bottle" is the one filled action, the heart sits beside it. Then "Bottles" (a group), a quiet list
of Finish, Colour and Collections (a 13px label over outlined chips), "Swatched on" rows led by the stack's
tip, a closed "Tip colour" disclosure, and the store link and SKU as footnotes.
A shade with a release date adds a footnote under that line, "Released 6 Jul 2019" in `--ink-2`, and its
official collection is the first chip of Collections (`.chip-long`: it wraps instead of running off the
screen, since a name can be 51 characters). A shade only the release sheet lists has no strip and no price:
the tip is the hero, "Not in the shop" is a quiet `--ink-2` word in the subhead (and in rows, where the
price would be), and the store link and SKU are absent.

**Lookup.** The camera is first: a 4:3 viewfinder (radius 16) with a "Scan the barcode" button on an idle tile
until the camera runs, a caption "Point at the barcode under the bottle", one field "Type the digits, a P code,
or a name", "Take a photo instead" as a text action, the result, and a "Learned codes" row. A result is a
group with the bottle photo (72 by 96) beside the shade's own `tip-l`, then the name, finishes and price.

**Sheets** (`<dialog>`): opaque `--surface`, top radius 20, a 36 by 5 grabber, a title row with a text
"Cancel", a sticky footer with the translucent material and the one filled button, padding to the home
indicator. Secondary actions are quiet text at the foot (`.sheet-quiet`), red only where the action destroys.

**Empty states.** One line and one action; where a drawing helps it is the thing that will fill the space (the
unpainted ring on Home and in Wheels, a nail outline in `--line-2` elsewhere), never foil.

## 7. The layer-stack builder

A sheet at `max-height: 92dvh`. Its head is the stack's composite tip (`tip-xl`) beside "Slot 3", the wheel name
as a caption and Cancel, with the summary under them as body text; every layer edit appends the new
composite over the old one and fades it in once loaded. Layers are a list on a 2px rail through their
tips: label (Base, 2nd, Top), name, an iOS-style hairline stepper for coats, move arrows from three layers on,
remove. Shortcuts (Over black, Copy from…, Same as last) are outlined chips that wrap. Then the search field
with the camera button, an Owned / Toppers / All segmented control, result rows with a trailing "+", a
disclosure for name and note, and the sticky "Save swatch".

## 8. Motion

Four moments, on `transform`, `scale` and `opacity`:
- Sheet: `translateY(100%)` to 0 over 380ms `cubic-bezier(.22,.9,.32,1)`, back over 240ms with
  `cubic-bezier(.68,0,.78,.1)`, the scrim fading with it (`@starting-style`, `allow-discrete`).
- Press: `scale(.96)` over 150ms ease-out; rows wash to `--fill` at once.
- A ring tip lifts to 1.08 before the sheet rises; a saved slot gets one foil sweep (700ms).
- A new builder tip fades in over the old one; the "+" of the Wheels list turns to ×.
Under `prefers-reduced-motion` there is no scale, slide or turn; the sheet fades over 150ms and the save ring
shows still for a second. Transitions name their properties (never `all`).

## 9. Copy

Sentence case everywhere. Buttons name the result and keep their name ("Add bottle", "Save swatch"). Errors
say what and how ("Coats must be 1 to 5."). Empty states are one line and one verb. Counts are plain
("13 of 20, 2 drafts", "9 bottles"). Section headings are nouns she would say: Bottles, Swatches, Swatched on.
"Wished" and "Owned ×2" are the two words for what she has and wants.

## 10. Checklist (390 by 844, light and dark)

No lilac or pink fill anywhere except the heart. One filled button per screen. No serif glyph, no webfont
request. Every list row shows a tip; no bottle photo outside the shade strip and the lookup result. Empty
slots on the ring carry no foil; the `?hl` ring is visible in both modes. The hub number is tabular and
centred. Chips are outlined and 44pt; the stepper is a hairline. The sheet clears the home indicator. The tab
bar's active tab is ink, not pink. Nested radii are concentric (16, 3 padding, 12). Dark surfaces carry the
ring, not a shadow. The reduced-motion run shows no sliding. The largest Dynamic Type size does not clip a
row name. No console error, no request that leaves the server except Shopify's image CDN.

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
