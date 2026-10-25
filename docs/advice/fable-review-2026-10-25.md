# Final visual review by Fable (claude-fable-5-1), 2026-10-25

Read-only review of the screenshots after stages 1-7 and the redesign. Item 3 accepted by the orchestrator (level control moves into the sheet).

**Inherited decisions**
- VISUAL.md is the contract for looks; DESIGN.md for behaviour. Five tabs, ring plus list, builder summary as hero, foil only on tips, status only when news, no red except danger, 44pt targets.
- Thumbnails must show polish, not backdrops. `thumb` already emits `crop=center`.
- Shade images: `hero_image_url` is position 1 only (`catalog/parse.py:46`); every tip, mini tip and layer tip reuses it.

**Diagnosis**
The identity has landed: pearl and plum, Fraunces names, hairline rows, foil on tips. Core pages are close to "very nice". Two things hold it back. First, every nail-shaped surface shows a rotated bottle photo, so the ring (the app's one bold idea) reads as a bowl of beans. The synthetic-gradient shots prove the ring and the stem bands work the moment the fill is a painted nail. Second, the builder, Bottles, Wishlist and shade detail each carry a heavy per-row control (segmented control, stepper, red ×), which contradicts "quiet wall, loud bottles".

**Drift / contradiction check**
- Red used for non-destructive actions: "Archive wheel", "Remove" on 8 wishlist rows, × on every layer. Checklist: nothing in a warning colour unless it is one.
- "In stock" shown on shade detail; VISUAL says silence is in stock.
- "I have this" vs "Add bottle" on the same button (`_shade_actions.html:5`); VISUAL says buttons keep their name.
- Hub repeats the page title. Offline and signed-out pages use the favicon tile as a 72px mark, which is the jelly bean §10 rejected.
- Bottles empty state has no button; VISUAL says one button.

**The nail fill fix (must)**
Pick a swatch image per shade at sync time, stored as `shade.swatch_image_url` in a new migration `005_swatch_image.sql` (add column, nullable; never edit 001). In `catalog/parse.py` add `swatch_image_url(images)` with a filename heuristic on the lowercased basename: reject anything containing bottle, brush, swipe, corner, side, collage, spill, gif; rank macro first, then hand, then swatch/nail/mani; take the lowest rank, earliest position. On the real snapshot this gives 235 of 250 products a nail image (165 macro, 63 hand, 7 swatch). Fallback: null, and the template uses the hero with a tighter crop zoomed on the polish: `thumb(hero, 102, 168)` stays but add `object-position: 50% 68%` on `.tip-art > img`, `.tip-mini img`, `.layer-tip img` so the cap is cropped out and the glass shows. The choice lives in sync, not templates, because the ring renders 20 tiles per paint and because a manual override column later (`swatch_image_override`) slots in beside it. Crop: `thumb(swatch, 102, 168)` for `_slot_tile.html:10,13`, `_slot_list.html:12`, `_stack_layers.html:15`, `_copy_sources.html:25`. Keep the image unrotated relative to the tip, which is already the case since the img sits inside the rotated slot. Stem bands keep using the same swatch crop. A CSS colour fill from an extracted colour is a later option, not needed once macros exist.

**Punch list**

1. Ring and builder tips: bottle photo in the nail shape. Fix above. Must.
2. Builder layer rows too heavy: stepper pill, two arrows, red × per row. Set `.layer-remove { color: var(--ink-2) }` with `--bad` only on `:active`; drop `.layer-coats` ("2 coats") since the stepper shows the count; hide move arrows unless there are 3 or more layers (`.rail:has(li:nth-child(3)) .layer-btn`). Must.
3. Bottles page and shade detail: a 4-segment level control in every card dominates both pages. In `_bottle_card.html` render the level as a single `.pill` ("Half") that opens the edit sheet, and keep the segmented control inside `_bottle_form.html` only. Replace "No P code" as the card title with the bought line, and show "No P code" as caption. Must.
4. Wishlist rows: 3-segment priority plus a full-width note input on all 8 rows. Make `.wish-note` a tertiary "Add a note" text button that reveals the input on tap (`<details>`), and set `.wish-controls .btn-danger` to `color: var(--ink-2)`. Must.
5. "I have this" / "Add bottle": always "Add bottle" in `_shade_actions.html:5`. Must (VISUAL §8).
6. Hub duplicates the title. `.hub-name` becomes the count in stat style (28/32, 600) and `.hub-count` the caption "of 20 swatched". Should.
7. "Archive wheel" in red (`.btn-danger` on wheel actions): archiving keeps tags working, so use `.btn-text` accent. Should.
8. Shade detail subhead shows "In stock": omit when `status.key == 'available'`, matching rows. Should.
9. "Owned ×2" pill orphaned under the buttons on shade detail: move it to the subhead after the price, or drop it since the Bottles list follows. Should.
10. Picker results show "Owned ×1" on every row while the Owned segment is active: hide `.pick-add .pill` when the filter is owned. Should.
11. Segmented selected thumb reads heavy in light: `.segmented` thumb has 3px transparent border plus shadow; drop the shadow to `0 1px 2px rgb(31 21 38 / .08)` and the border to 2px. Should.
12. Search focus ring in the builder is a thick double outline (`.search-field:focus-within` 2px plus pill edge). Use `outline-offset: -2px`. Should.
13. Offline and signed-out mark: `status-mark` loads `favicon.svg`, the bean. Point it at `apple-touch-icon.png` (the finger and foil nail), radius 18. Should.
14. Bottles empty state has no button: add "Add a bottle" linking to lookup. Should.
15. Lookup page has two near-identical primaries ("Scan the barcode", "Take a photo of the barcode"). Make the second tertiary text, and shorten the helper to "Or type the digits under the barcode, a P code, or a name". Should.
16. Wheel list rows repeat "25 Oct 2026" on every row: keep the date only when it differs from the previous row, or show it in the builder only. Nice.
17. Home: gap between search and "Recent bottles" is about 48px against a 32 section rhythm; set the shelf section `margin-top: 32px`. Nice.
18. Builder sheet title: "Holos" with caption "Slot 12". The slot is the subject; swap so the title is "Slot 12" and caption "Holos". Nice.
19. Twelve-slot ring (Winter ombré) leaves wide gaps; scale `--ring` down with `.ring-n-12 { --ring: 120px }`. Nice.
20. Tag page "New tag URL" in red is right, but "Take the tag" secondary and "Open the wheel" primary sit between two sections; move "Open the wheel" to the top under the address. Nice.

**Verdict**
Not yet, but close. The quiet pages (Home, Shades, Shade detail strip, error pages, Wheels list) already look like a boutique app, and dark mode holds up everywhere with a legible `?hl` ring. What drags it down is that the loudest surfaces are controls, not polish: steppers, segmented pills and red marks repeated down the page, and a ring of sideways bottles where the painted nails should be. The single change that lifts it most is the swatch image column: once each tip shows a macro of the polish on a nail, the ring becomes the hero the design promised and the builder's rail reads as one painted nail, which is the "intuitive" feeling Jan is asking for.

**Risks**
- Filename heuristic covers 235 of 250 in page 1; pages 2 and 3 may have older naming, so the fallback crop must look acceptable on its own.
- Hand photos cropped to centre may show skin rather than nail; macros are safer, so rank them first and allow the override column later.
- Demoting the bottle level control to a pill adds one tap to change level; acceptable since Edit already opens the sheet.

**Need from main agent**
None. The only decision is whether to accept item 3 (level control moves into the sheet); default is yes.
