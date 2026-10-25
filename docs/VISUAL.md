# polished: visual design

Written by the design advisor (Fable, claude-fable-5-1) on 2026-10-25 from the frontend-design and
apple-design skills in `.pi/skills/`, against screenshots of stages 1-4. Decisions taken by the
orchestrator after it: the tab bar has five tabs (Home, Shades, Bottles, Wheels, Wishlist) because
"what do I own" is a primary question and Bottles also holds the purchase history; the wheel page is
the ring plus the list (DESIGN.md section 9 follows). Shopify `width`/`height`/`crop=center`
thumbnails were verified on a real image the same day. DESIGN.md wins on behaviour; this file wins
on looks.

## 1. Concept

**"A pearl gallery for loud bottles, and one wheel of nail tips."** Every Holo Taco photo is already shouting, so the app is the quiet wall: cool pearl in light, oil-slick plum in dark, hairlines instead of boxes, and type with a boutique voice. The one place boldness is spent is the **nail tip**: the swatch wheel renders as an actual ring of twenty tips, and the only shimmer in the app is a holographic foil that lives on tip edges (empty slots, highlight ring, save flash, logo). Nothing else shimmers.

Review against defaults, and what changed: the first pass had a cream ground and stat cards. Cream went to a cool pearl (`#FAF7FB`, violet-leaning, because polish photography is cool-lit), cards went to plain numbers on hairlines, every middle dot became a sentence, the chip kit left the list rows, and the accent stayed raspberry because that is Holo Taco's own vocabulary, not a default.

## 2. Tokens

Light: `--bg #FAF7FB` pearl page, `--surface #FFFFFF` sheets and grouped lists, `--fill #F1EAF3` pressed rows and tinted controls, `--ink #1F1526` text, `--ink-2 #6F6277` secondary, `--line #E7DEEA` hairlines, `--accent #A8246F` raspberry (7:1 on white) for actions and the heart, `--accent-tint rgba(168,36,111,.12)`, `--ok #1E7A4C`, `--warn #9A5A00`, `--bad #B3261E`.

Dark: `--bg #120C16`, `--surface #1B1320`, `--fill #261C2B`, `--ink #F4ECF5`, `--ink-2 #AFA2B5`, `--line #33283A`, `--accent #F06BB0`, `--accent-on #1A0F1F`, `--ok #5FCF95`, `--warn #F0B05A`, `--bad #FF8A80`. Set `color-scheme` and both `theme-color` metas to match.

Holo foil: `--foil: conic-gradient(from 200deg, #FFB3C7, #FFE29A, #B7F5C8, #9FD8FF, #D3B4FF, #FFB3C7)`. Used as a 2 to 3px ring (via `mask` or a padded pseudo-element) on empty nail tips, the `?hl` ring, the save flash, the empty-state glyph and the logo. Never on text, buttons, backgrounds, chips or dividers.

Type: two families. **Fraunces** (OFL, github.com/undercasetype/Fraunces, or Google Fonts) as a single variable woff2 subset to latin with `pyftsubset` (about 60 KB), served from `/static/fonts/`, `font-display: swap`, precached by the service worker. It carries shade names and page titles only, set with `font-variation-settings: "SOFT" 50, "opsz" 24`. Everything else is `system-ui` (SF Pro on iPhone: optical sizes, Dynamic Type, zero bytes), per the Apple skill.

| Role | Face | Size/leading | Weight | Tracking |
|---|---|---|---|---|
| Large title | Fraunces | 34/38 | 600 | -0.015em |
| Shade title (detail) | Fraunces | 28/32 | 600 | -0.01em |
| Row name, stack summary | Fraunces | 19/23 | 500 | 0 |
| Headline, buttons | system | 17/22 | 600 | 0 |
| Body | system | 17/22 | 400 | 0 |
| Subhead (status, price) | system | 15/20 | 400 | 0 |
| Caption, chips | system | 13/16 | 500 | +0.01em |
| Stat number | system | 28/32 tabular | 600 | -0.01em |

Spacing scale 4, 8, 12, 16, 24, 32, 48. Page gutter 16. Row padding 12 vertical. Section gap 32.

Radii, by hierarchy: pills 999 (chips, segmented controls, grabber); 10 small thumbs; 12 row thumbs; 14 buttons and inputs; 18 grouped lists, bottle cards, the checkout box, gallery images; 24 sheet top corners; nail tips use their own shape (section 5).

Materials and shadows. No shadows on cards; rows separate with hairlines. Tab bar and sticky search: `rgba(250,247,251,.78)` light, `rgba(18,12,22,.72)` dark, `backdrop-filter: blur(20px) saturate(1.6)`, 1px top edge `rgba(31,21,38,.08)`. Sheet: opaque surface, scrim `rgba(31,21,38,.45)` light and `rgba(0,0,0,.6)` dark, shadow `0 -12px 48px rgba(31,21,38,.22)`. Every image gets a mat ring `box-shadow: inset 0 0 0 1px rgba(31,21,38,.10)` (white at .12 in dark), which is what stops loud photos from bleeding into the page. Under `prefers-reduced-transparency` the materials go solid.

## 3. App chrome

Bottom tab bar, 49pt plus `safe-area-inset-bottom`, four tabs: Home, Shades, Wheels, Wishlist. Icons are an SVG sprite at `/static/icons/ui.svg` used via `<use>`; labels in caption size; active tab in accent. The top text bar goes away. Each page opens with an iOS-style large title, left-aligned, in Fraunces; pages that need a back link get a 44pt row above it with a chevron and the parent name. Scan is a 44pt camera button at the trailing edge of the search field on Home and Shades, plus the big "Scan a bottle" button on Home. The search field is sticky under the status bar and becomes material only when stuck (a one-line IntersectionObserver sentinel). Sign out moves to the Home footer. Bottles is reached from the Home numbers and from each shade page.

## 4. Components

**Shade row.** Thumbnail 48×64 from the CDN as a true crop, not a CSS zoom: extend `thumb` to emit `width=144&height=240&crop=center`, which keeps the bottle and discards most of the backdrop. Radius 12, mat ring. Name in Fraunces 19. Second line in subhead: finishes as plain words ("Glitter, holographic"), then price, tabular. Status appears only when it is news: sold out or retiring in `--bad`/`--warn`; in stock says nothing. Owned shows a small ink pill "Owned ×2" in `--fill`; wishlisted shows an accent heart.

```
┌────┐  8-Bit Blues
│ ▓▓ │  Glitter, holographic      $15.50
│ ▓▓ │  Owned ×1  ♥
└────┘ ──────────────────────────────────
```

**Chips** (detail page only): pill, 36pt tall, `--fill` ground, ink text, caption weight; selected in `--accent-tint` with accent text. **Buttons**: primary accent fill, 50pt, radius 14, white 17/600, `:active` `scale(.97)` over 100ms; secondary is `--accent-tint` with accent text, no border; tertiary is plain accent text. Icon buttons are 44×44 with `aria-label`.

**Bottom sheet.** Opaque surface, top radius 24, a 36×5 grabber in `--line` 8pt from the top, title row with a text "Cancel" at the right, sticky footer with the material and the primary button, padding to the home indicator. Motion in section 7.

**Wishlist checkout box.** A tinted card (`--accent-tint`, radius 18): a 3-segment pill control for priority, the total in the stat style, "Open in Holo Taco checkout" primary, "Copy the list" tertiary, and the copyable names as a plain caption list with no border. Summary line above becomes prose: "4 shades, $61.00. 3 are in stock now for $46.00."

**Home.** Large title with the 28px logo mark; search; a shelf: horizontal scroll of recent bottles as 72×96 crops with names under them; one numbers row (bottles, shades owned, on the wishlist) set as stat numbers over captions with hairlines, no boxes; a grouped list (surface, radius 18) of shortcuts with chevrons; footer "Signed in as Dev. Sign out".

**Shade detail.** Image strip runs edge to edge, images 3:4 at 70vw, radius 18, snap, first image aligned to the gutter. Then title, a subhead row with price and any status, actions (Add bottle primary two-thirds, heart secondary one-third), bottles grouped list, chip rows for finish, colour, collection, and "Swatched on" rows linking to the wheel with `?hl=`.

**Empty states.** A 64px nail-tip outline stroked in foil, a headline, one line, one button. "No bottles yet. Scan the code under a bottle or add it from its shade page."

## 5. The swatch wheel

A ring, because her wheel is a ring. Container `aspect-ratio: 1; width: min(100% , 360px)`; each slot `position: absolute` at the centre with `transform: rotate(calc(var(--i) * 18deg)) translateY(calc(-1 * var(--ring)))`, slot 1 at twelve o'clock, clockwise. `--ring` is 132px at 390pt (scales with viewport width minus gutters). The tip is 34×56 with `border-radius: 50% 50% 38% 38% / 62% 62% 30% 30%`, free edge outward; the button around it is 44×64 so the hit areas tile the ring at 42pt pitch. The hub (about 150px) holds the wheel name and "12 of 20 swatched".

Filled tip: the top layer's crop (`width=102&height=168&crop=center`) fills the shape; lower layers show as 6px bands at the stem, base first, at most three, so a two-layer stack reads as topper over base. Empty slot: the number in `--ink-2` on `--fill` with a 1.5px foil edge. Draft: an 8px accent dot at the stem. Highlight (`?hl`): matching tips get a 3px foil ring and the rest drop to 55 percent opacity. Below the ring, a plain list of filled slots with number, the summary in Fraunces and three 24×32 mini tips, so the stack can be read without squinting; both the ring and the list open the builder.

```
          (1)(2)
      (20)      (3)
    (19)  Holos   (4)
   (18)  12 of 20  (5)
    ...            ...
```

Section 9 of DESIGN.md changes from "4-column grid" to "ring plus list" in the same commit.

## 6. The layer-stack builder

Sheet at `max-height: 92dvh`. Header: wheel name, "Slot 12" caption, Cancel. The live summary sits directly under it in Fraunces 19 and is the hero of the screen; it rerenders out of band as today. Layers are a vertical stack with a left rail: each row shows the layer label (Base, 2nd, Top) in caption, a 32×44 mini tip with that layer's crop, and the name; the rail draws a 2px line through the tips so the list reads as one painted nail, bottom to top. Controls go on a second line so everything stays 44pt on 390: a −/count/+ stepper as a pill (108pt wide), up and down icon buttons, remove at the trailing edge. Templates are a horizontal row of tinted pills: Over black, Copy from…, Same as last. Then the search field with the camera button, an Owned / Toppers / All segmented control, and compact result rows (40×52 thumbs) with a trailing "+" so adding is one obvious tap. Name and note live under a disclosure above a sticky Save.

```
Holos, slot 12                               Cancel
One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco
Base ▐▓▌ One-Coat Black
     ( − 1 + )           ↑   ↓          ×
2nd  ▐▓▌ Spirit Fingers
     ( − 2 + )           ↑   ↓          ×
Top  ▐▓▌ Flakie Holo Taco
     ( − 1 + )           ↑   ↓          ×
[Over black] [Copy from…] [Same as last]
[🔍 Search shades or a P code            📷]
(Owned)(Toppers)(All)
▓ Absolutely Cooked                          +
▓ Acid Drip                                  +
Name and note ▾
[ Save swatch ]
```

## 7. Motion

Four moments, all CSS, all on `transform` and `opacity`:
- Sheet open: `translateY(100%)` to 0 over 380ms `cubic-bezier(.22,.9,.32,1)` (a critically damped spring near response 0.35), scrim fades 240ms. Close over 240ms with the mirrored curve `cubic-bezier(.68,0,.78,.1)`. Implemented with `@starting-style` and `transition-behavior: allow-discrete` on `dialog[open]` and `::backdrop`; browsers without it just show the sheet.
- Layer added: the server marks the newest row `is-new`; it enters with opacity 0 and `translateY(-6px)` over 240ms, same curve.
- Save: the out-of-band slot tile gets `is-saved`, and a foil ring sweeps once around the tip over 700ms, then settles to the normal state.
- Press: buttons `scale(.97)` over 100ms on `:active`; rows fill with `--fill` on `:active` with no delay; `-webkit-tap-highlight-color: transparent`.

Under `prefers-reduced-motion`: every transform is removed and each moment becomes a 150ms opacity change; the save ring shows static for one second and fades.

## 8. Copy and voice

Sentence case everywhere, no caps labels, no middle dots, no spaced dashes. Buttons name the result and keep their name: "Add bottle" then "Bottle added", "Save swatch" then "Swatch saved". Errors say what and how: "Coats must be 1 to 5." Empty states are one line and one verb. Loading ends with "…". Numbers keep a non-breaking space before units. Section headings are nouns the user would say: Bottles, Finish, Colour, Swatched on.

## 9. Implementation order and checklist

1. Tokens, fonts and type scale; tab bar and large titles; remove the top bar. This alone changes the app's identity.
2. Thumbnail crop in `thumb`, mat rings, new row layout, status and chips demoted.
3. Buttons, segmented controls, inputs, badges.
4. Sheet: grabber, radius, scrim, motion, sticky footer.
5. Shade detail strip and sections. 6. Home shelf and numbers; wishlist box. 7. Logo and icon sprite. 8. Wheel ring and builder (stages 6 and 7 of PLAN.md), with the DESIGN.md edit.

Screenshot checklist at 390×844, light and dark: thumbnails show bottles, not backdrops; no element shares a radius with a different tier; no bordered card except the sheet and grouped lists; nothing is green unless it is a success; no caps, no middle dots; every tappable thing measures 44pt; one serif role per screen (names and titles only); the foil appears only on tips; the sheet clears the home indicator; the `?hl` ring is visible in both modes; the reduced-motion run shows no sliding.

## 10. Logo

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

## Risks

- Fraunces is a serif; if the implementer drifts the palette warm it becomes the generic editorial look. The pearl and plum tokens are the guard.
- A 20-slot ring at 42pt pitch is at the edge of the 44pt guideline; the list below is the safety net and must ship with the ring.
- `@starting-style` on dialogs needs iOS 17.5 or later; older devices get no sheet motion, which is acceptable.
- Shopify `crop=center` behaviour on this CDN should be verified on one real image URL before building rows around it.
