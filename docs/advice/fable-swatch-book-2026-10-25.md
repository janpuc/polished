# "The swatch book": design direction by Fable (claude-fable-5-1), 2026-10-25

Written with the impeccable and Krehel skills after Jan said the app was "a bit ugly ... it should be beautiful, not just pretty". Decision taken by the orchestrator: tips replace bottle thumbnails in all lists (confirmed).

## Inherited decisions

- Operate surface, iPhone home-screen PWA, HTMX + hand CSS, CSP with no inline styles. Five tabs. Ring plus list on the wheel page. Builder is a bottom sheet with a server-side draft. Sentence case, no middle dots, no caps labels. Logo is a holo nail on plum and is already shipped as the icon.
- Painted-nail SVG tips now exist per shade and per stack (`tips.py`, `_tip_img.html`), fed by `swatch_hex` / `swatch_hex2` / finish tags, with a household override. This is new since VISUAL.md was written and it changes what the app's content is.
- VISUAL.md concept: "a pearl gallery for loud bottles", Fraunces for names and titles, raspberry accent, lilac fills, foil only on tips.

## 1. Critique

Method: design review only, single context (no detector, no sub-agents available in this role).

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | System status | 3 | drafts resume, counts, notices; no skeletons |
| 2 | Real world | 3 | good language; "P code", "Slot 3" fine for her |
| 3 | Control | 3 | Cancel, drafts, archive not delete |
| 4 | Consistency | 2 | serif role drifts; accent on three button tiers; sheet titles sans, page titles serif |
| 5 | Error prevention | 3 | steppers clamp, hx-confirm |
| 6 | Recognition | 3 | |
| 7 | Flexibility | 3 | scan, P codes, templates, Same as last |
| 8 | Aesthetic | 2 | the complaint; see below |
| 9 | Recovery | 3 | "Coats must be 1 to 5" |
| 10 | Help | 2 | tag page only |
| | Total | 27/40 | Acceptable |

Specificity verdict: strip the photos and this could be any Shopify companion app. The one authored thing, the ring, lives on one page.

Why it reads "pretty but a bit ugly", screen by screen:

- **Two pinks on every screen.** Lilac `--fill #F1EAF3` (search field, chips, steppers, inputs) sits beside raspberry `--accent-tint` (Wishlist button, template chips, notices, the whole checkout box). They are within a hue family but not the same colour, so every screen has a near-miss. Shade detail light: lilac "Owned ×1" pill, pink "Wishlist", lilac finish chips in one viewport.
- **The accent is everywhere, so it has no force.** Bottles light: seven "Archive" texts, a camera, the active tab and the "Low ›" pills all in raspberry; the level, the one fact she needs, is the smallest element. Wishlist: pink box, pink button, pink link, pink "I bought these", four pink "Add a note", a selected pink segment. Krehel: fill exactly one action per view.
- **Bottle thumbnails are backdrops, not colours.** Shades list: pink sky, broken glass, pop-art, a product box. Home shelf: three black boxes in a row. At 48×64 the polish is a sliver; a nail person identifies a shade by its swatch. The row identity is noise.
- **Serif fatigue.** Fraunces is on every row title (`app.css:777`), every group head, every wishlist row, every builder layer, plus the summary and the page title: six to nine serif lines per screen. VISUAL said one serif role per screen; names are everywhere, so the rule never held. At 19px with SOFT it turns "Overstimulated.exe" and "Aura Farming" into a bistro menu, fighting the names' voice. Fraunces is also on Impeccable's named-default list.
- **Pill everything.** Search, chips, segmented, steppers, level pills, owned pills, grabber: one shape in one lilac. The wishlist nests a pill segmented control inside an 18px card with 16px padding (non-concentric).
- **Flat rhythm.** `section-title` margin 1.75rem above every section, so Home reads shelf, stats, button, list at equal weight. Home is a settings page: "Add a shade by hand", "Catalog sync" sit where the collection should be.
- **Light mode has three near-whites** (bg, surface, fill) and no edge; grouped lists float. Dark mode is better composed than light, which is a tell that the light palette is the weak one.
- **The ring is good but under-staged.** 360px max, 136px radius, seven foil-edged numbered empties make a rainbow circus around the hub; the hub text "of 20 swatched" repeats the title. Nothing holds the tips: a real swatch wheel has a ring they sit on.
- **Builder:** the summary is text; the painted nail, now drawable, is absent from the head. Stepper pill plus two pink template chips plus a pink notice in one viewport.
- **Tab bar:** fine. Keep it.

## 2. Decision: replace

The incumbent concept was built for bottle photos as content; the content is now a drawable painted nail. Its weaknesses are the world itself (lilac and raspberry, serif names, pill fills, photos as identity), not drift from it. Refining would be polish on a discarded look. Keep product truth, copy voice, the ring plus list, the builder structure, the tab bar, the logo and the dark plum family that already matches the logo.

**Concept: "The swatch book."** A nail tech's colour chart: every shade in the app is a painted tip, laid on a quiet matte board in light and on the logo's plum in dark. The chrome is ink and board only. Colour comes from the tips. Pink means one thing: wanted.

**Palette** (OKLCH, hue 335, measured; all body pairs ≥4.5:1):

| Role | Light | Dark |
|---|---|---|
| `--bg` board | #F6F2F5 | #160B14 |
| `--surface` | #FDFBFC | #20131D |
| `--fill` component bg | #ECE5EA | #30212C |
| `--fill-2` pressed/selected | #E3DBE1 | #3A2B36 |
| `--line` hairline | #DDD5DB | #372834 |
| `--line-2` input border | #C5BAC2 | #4D3C49 |
| `--ink` | #261322 | #F7EFF5 |
| `--ink-2` secondary | #6B5666 (6.0:1) | #B7A4B2 (8.2:1) |
| `--ink-3` large/icons only | #8C7A87 | #92808D |
| `--primary` fill, `--primary-on` | #381531 / #FFFFFF | #F7EFF5 / #280C23 |
| `--heart` icon / text | #D83486 / #B8196F | #FF77B4 |
| `--ok` `--warn` `--bad` | #007840 #975800 #BE222A | #61DA92 #F9B64F #FF7F7F |
| `--foil` | unchanged conic | unchanged |
| `--mat` image outline | oklch(0 0 0 / .1) | oklch(1 0 0 / .1) |

Rules: `--primary` is the cap of a Holo Taco bottle, one filled action per view, selected state (segment, chip, active tab) is `--primary` fill with `--primary-on` text. Links and text buttons are `--ink` at 600. Pink only on the heart and wishlist count. Foil only on tips: highlight ring, save sweep, the logo. Never on empties.

**Typography: SF Pro only** (`system-ui`), no webfont. Argument: Operate surface; iOS skill says SF carries the UI; it ships optical sizes, Dynamic Type and zero bytes; the names are loud enough; the display moment belongs to the tips, not to letterforms. A second face would need a role only it can perform, and there is none left. Delete the `@font-face` and preload.

| Role | Size/leading | Weight | Tracking |
|---|---|---|---|
| Large title | 34/41 | 700 | -0.02em |
| Shade title (detail), sheet title | 28/34 | 700 | -0.02em |
| Section | 22/28 | 600 | -0.01em |
| Row name, headline, buttons | 17/22 | 600 | 0 |
| Body | 17/22 | 400 | 0 |
| Subhead (finishes, price) | 15/20 | 400 | 0 |
| Footnote (dates, notes) | 13/18 | 400 | 0 |
| Caption (tab labels, layer labels) | 12/16 | 500 | 0 |
| Hub number | 44/48 | 700, tabular | -0.03em |

`font-optical-sizing: auto`, `tabular-nums` on prices and counts, `text-wrap: balance` on titles, `pretty` on body.

**Spacing** 4, 8, 12, 16, 24, 32, 48. Gutter 16. Within a group 8, between groups 24, section gap 32 with 12 under the section heading. Row padding 12 vertical, 16 horizontal.

**Radii** tips their own shape; 10 inputs, search and chips (not pills); 12 buttons; 16 groups with 4 padding so nested rows are 12; 20 sheet top; 999 only for the segmented control and the grabber.

**Materials** tab bar and sheet footer stay translucent (keep the current recipe). Groups: `--surface` plus `0 0 0 1px oklch(0 0 0 / .06)` ring in light, a white ring at .08 in dark (Krehel's shadow-border), `border: 1px solid transparent` under it. No card shadows otherwise. Lists sit on the board with hairlines.

**Tips as the identity** (the signature): four sizes, `tip-s` 28×46 (inline, bought sheet), `tip-m` 40×66 (rows), `tip-l` 56×92 (detail, wheel list), `tip-xl` 72×118 (builder head). Each is the painted SVG with a 1px `--mat` inset and a 1px bottom-right inner highlight so it reads glossy. Bottle photos remain only on the shade detail strip and the lookup result. A shade with no colour yet shows a neutral tip with a small "set colour" affordance on detail.

**Iconography** keep `ui.svg`, one stroke, 1.75px at 24 to match 500-weight labels, `currentColor`, fill variant for the active tab.

**Motion** keep the four moments. Press `scale: .96` 150ms ease-out, `:not(:disabled)`. Sheet: `translateY(100%)` to 0 over 380ms with the existing curve. Save: foil sweep (keep). New: tapping a ring tip lifts it (`scale 1.08`, 150ms) before the sheet rises. Theme switch suppresses transitions. Reduced motion: opacity only.

## 3. Screens (390pt)

**Home**
```
Polished                                   [scan]
[ Search 372 shades                            ]
                 ( ring: Holos, 200px )
            Holos  ·  13 of 20       ›
On your nails lately
 ▐▓▌   ▐▓▌   ▐▓▌   ▐▓▌   ▐▓▌      (tip-l, names under)
 Flakie Spirit  One-Coat Retina  This Is
7 bottles · 6 shades · 6 wished            (links)
Browse all shades                            ›
Toppers                                      ›
New and in stock                             ›
More  (add by hand, catalog sync, sign out)  ›
```
Decisions: the last-opened wheel is the first viewport, small; recent bottles are tips; stats become one line; admin links collapse into More; wordmark in SF 700 beside the icon.

**Shades**
```
Shades                                        +
[ Search shades                       ] [filter]
372 shades
▐▓▌  8-Bit Blues                        $15.50
     Glitter, holographic
▐▓▌  Acid Drip                     ♥    $15.50
     Holographic, metallic              ×2
```
Decisions: tip-m in place of the thumbnail; name 17/600 sans; price tabular right; owned count as "×2" footnote at the trailing edge; heart pink only; status words in `--bad`/`--warn` with no fill; hairlines, no cards.

**Shade detail**
```
‹ Shades
[ photo ][ photo ]   (edge to edge, keep)
▐▓▌  Overstimulated.exe
     $15.50 · Owned ×1           (tip-l beside title)
[ Add bottle ]                         ( ♥ )
Bottles
 P259   Half ▮                 Bought 2 Aug 2026
Finish    Glitter   Matte             (outlined chips)
Collections ...
Swatched on   Holos, slot 1                   ›
```
Decisions: the app's own tip next to the brand's photo; one filled action; heart is an icon button, pink when on; chips outlined with `--line-2`; bottle level drawn as a small bottle glyph filled to Half in the shade's colour.

**Bottles**
```
Bottles                                    [scan]
( Collection | History )                   (segmented)
All  Full  Half  Low  Empty                (outlined chips)
▐▓▌ Aura Farming
    P311          Half ▮                     ›
    Bought 12 Mar 2026   Low ▮               ›
▐▓▌ Flakie Holo Taco
    P95           Low ▮                      ›
```
Decisions: tip-m group heads; the level glyph is the only colour in the row; Archive moves into the edit sheet; rows open the sheet with a chevron; no accent text at all on this page.

**Wishlist**
```
Wishlist
$87.50 for 6 shades, all in stock
[ Open in Holo Taco checkout ]     Copy list
( Want most | Plus would like | Everything )
Want most 2
▐▓▌ Acid Drip                    $15.50
    For the autumn wheel          Want most ⌄
▐▓▌ Hyper Punch                  $16.50
    Add a note                    Want most ⌄
```
Decisions: the checkout box becomes a short head on the board, not a tinted card; one filled button; priority per row is one compact select instead of a three-segment control; Remove moves into the row's sheet; notes as footnote text.

**Wheels**
```
Wheels                                        +
(◌ mini ring)  Holos
               13 of 20, 2 drafts             ›
(◌ mini ring)  Winter ombré
               6 of 12                        ›
```
Decisions: each wheel is its own real tips at 72px; "New wheel" is the + in the title row; nothing above the content.

**Wheel page**
```
‹ Wheels
Holos
            ( full-width ring, radius 150
              hairline ring through the stems
              empties: fill + small number, no foil
              hub: 13 large, "of 20" footnote )
Swatches
 1  ▐▓▌  Overstimulated.exe ×2        11 Oct
 3  ▐▓▌  One-Coat Black ×2 + This Is Fine ×2 + ...
This wheel   Tag and QR · Rename · Archive
```
Decisions: ring width `min(100% , 390px)`, tips 38×62; a 1.5px `--line` circle at `--ring - 22px` holds the tips like the plastic ring; foil only for `?hl` and the save sweep; hub is number only; list rows show the composite stack tip at tip-m.

**Builder sheet**
```
━━
▐▓▓▌  Slot 3 · Holos                      Cancel
▐▓▓▌  One-Coat Black ×2 + This Is Fine ×2 +
      Flakie Holo Taco          (tip-xl composite)
Base ▐▓▌ One-Coat Black     [ − 2 + ]   ↓   ×
2nd  ▐▓▌ This Is Fine       [ − 2 + ]  ↑ ↓  ×
Top  ▐▓▌ Flakie Holo Taco   [ − 1 + ]   ↑   ×
Over black   Copy from…   Same as last   (outlined)
[ Search shades or a P code              ] [scan]
( Owned | Toppers | All )
▐▓▌ Aura Farming                             +
[ Save swatch ]
```
Decisions: the live composite tip is the hero and re-renders out of band with a crossfade; iOS-style stepper with hairline; the "Resumed your draft" note becomes a footnote under the title, not a tinted block; one filled button.

**Lookup / scan**
```
‹ Bottles
[   camera viewfinder, 4:3, rounded 16     ]
   Point at the barcode under the bottle
[ Type the digits, a P code, or a name    ]
Learned codes                                 ›
```
Decisions: camera first when `scan=1`; one input; no stacked buttons; the result card shows the tip beside the bottle photo.

## 4. Implementation plan

Run 1, tokens and components (one worker run):
1. Replace the token block (`app.css:14-85`) with the palette above; delete `--accent-tint`, `--serif`, the `@font-face`, the preload in `base.html`, and `fraunces-latin.woff2`.
2. Type scale as roles; remove every `font-variation-settings` and `var(--serif)` (6 sites).
3. Controls: `.btn` primary = `--primary`; secondary = `--fill` with ink text; `.btn-text` = ink 600; chips outlined; segmented selected = primary fill; stepper hairline; inputs 10 radius with `--line-2`.
4. Tip component sizes and the gloss highlight; swap `.thumb` for `shade_tip` in `_shade_row_body.html`, the Home shelf, `_bottle_groups.html`, `_wishlist_row.html`, `_bought_sheet.html`, `_picker_results.html`.
5. Ring: hairline ring, empties without foil, hub number only, radius 150.
6. Screenshots, both modes.

Run 2, screens: Home restructure; Wheels mini rings; Bottles level glyph and Archive into the sheet; Wishlist head and row controls; builder head composite; lookup camera-first; shade detail tip beside title; rewrite VISUAL.md from the built result and amend DESIGN.md 9 to 10 in the same commit.

Screenshot checklist, light and dark at 390×844: no lilac or pink fill anywhere except the heart; one filled button per screen; zero serif glyphs; every list row shows a tip, no bottle photo outside detail and lookup; empties on the ring carry no foil; `?hl` ring visible in both modes; hub number tabular and centred; chips outlined and 44pt; stepper hairline; sheet clears the home indicator; tab active state is ink, not pink; nested radii concentric (16/4/12); dark surfaces carry the white ring, not a shadow; reduced-motion run shows no sliding; Dynamic Type at the largest accessibility size does not clip row names.

Anti-patterns to refuse: eyebrow labels (craft-floor ban); kickers above headings; coloured `border-left`; gradient text; glass as decoration; emoji as icons; zero-offset halos; `transition: all`; press scale below .96; hover rules outside `@media (hover: hover)`; foil on chrome; a second accent; tinted notice boxes; same-size card grids; the stat-block hero.

## Risks

- `swatch_hex` is read from photos and can be wrong or neutral for some shades; a wrong-colour tip in a list is worse than a photo. Mitigate: the override already exists; show "set colour" on detail; audit the 372 colours once before shipping run 1.
- SF-only can read plain if spacing and weight are sloppy; the beauty is carried by tips, ink discipline and precise rhythm, so run 1 must land all three together.
- A full-width ring at radius 150 brings tip pitch to about 47pt, which helps the 44pt target; verify on a real phone.

## Need from main agent

One decision before run 1: confirm tips replace bottle thumbnails in all lists (the pivot the whole world rests on). Everything else follows from it.
