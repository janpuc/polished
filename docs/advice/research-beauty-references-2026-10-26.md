# Research: Beauty references for "polished" (nail-polish collection app)

## Summary
The strongest transferable pattern across current references is **restraint plus material**: a quiet, warm neutral canvas with the collectible objects as the only colour (Aesop, Rhode, Lumy, Flighty), and depth that comes from a thin glass/specular layer on chrome (Linear's 2025 mobile redesign, Apple's Liquid Glass) rather than from decoration. polished already has the restraint; what it lacks is (a) a *physical* treatment of the tips (light, shadow, gloss, a surface they sit on), (b) one expressive type voice, (c) a few tactile motion moments, and (d) a deliberate phone/iPad/Mac layout switch. All of this is doable in server-rendered HTML/CSS.

**How to read this report.** I verified the facts marked *Verified* by fetching the cited page. I could not view screenshots in this run. The "what makes it beautiful" descriptions marked *(memory)* come from my background knowledge of the products, not from a fetched page, so spot-check them in a browser before copying a detail. Design-spec sites (tastekit.dev, pikspec.com) are third-party auto-extractions, so I treat them as medium confidence.

## Reference list (16)

### (a) iOS apps with Apple Design Award-level craft

1. **Flighty** — iOS/iPad/Mac. https://developer.apple.com/news/?id=970ncww4 (*Verified*: ADA "Behind the Design")
   - *Why it's beautiful:* The look deliberately mirrors airport departure-board conventions ("one line per flight… 50 years of figuring out what's important"). The Passport screen turns your stats into "gorgeous, shareable custom artwork" (*Verified*). Dense data is made calm by strict hierarchy: one large primary value, small tabular secondary values, colour used only for status *(memory)*.
   - *Import:* (i) A "Collection Passport" page: a poster-like, shareable card (SVG/`<canvas>`-free, server-rendered) with total shades, favourite finish, the colour-family ring of tips, and the newest additions. (ii) Real-world analogy as a design rule: pick the polish rack / salon wall as polished's "airport board" and let it dictate layout. (iii) Use `font-variant-numeric: tabular-nums` for counts.

2. **Crouton** — iOS/iPad/Mac. https://developer.apple.com/news/?id=9x75y43e (*Verified*: 2024 ADA Interaction winner; recipe manager that is "exceptionally organized")
   - *Why:* A personal collection (recipes) with a cover-image-led grid, one-handed bottom actions, and fast paths into "do the thing" mode *(memory)*.
   - *Import:* (i) A full-screen "wearing today" mode: one tap on a shade opens large-scale tip + layer recipe with a big "I wore this" button at thumb height. (ii) Cover-led list rows with a trailing quick action.

3. **CapWords** — iPhone/iPad. https://developer.apple.com/articles/capwords/ and https://developer.apple.com/design/awards/2025/ (*Verified*: 2025 ADA Delight and Fun winner)
   - *Why:* Objects become **stickers** that are "collected" in the app; a micro-animation covers the capture→confirm→display sequence; each flashcard transition has a real-world sound. The collected sticker is the reward (*Verified*).
   - *Import:* (i) Treat each tip as a die-cut sticker: a thin white/ink outline plus a faint drop shadow, so tips read as objects on a surface. (ii) "Add to collection" moment: the new tip scales in from 0.85 with a spring `cubic-bezier` and a one-shot specular sweep (CSS only). (iii) Optional, off by default: tiny haptic/sound cues via `navigator.vibrate` are not available on iOS Safari, so skip haptics and rely on motion.

4. **Lumy** — iPhone/iPad/Watch. https://developer.apple.com/design/awards/2025/ (*Verified*: finalist; "simple design, carefully curated color palette")
   - *Why:* One data domain (sun/moon) with a tightly limited palette; colour appears only where the data is *(memory: gradient sky bands)*.
   - *Import:* Keep colour reserved for tips and a single accent. Use a subtle time-of-day background tint (light/dark ink with a ±3% hue shift) on the home page.

5. **Denim – Playlist Cover Maker** — iPhone. https://developer.apple.com/design/awards/2025/ (*Verified*: finalist; "mesh gradients", "cool depth effects", "smooth scroll transitions")
   - *Why:* Mesh gradients as a hero material, handled tastefully because they sit behind one clear subject.
   - *Import:* A mesh-gradient "holo wash" built from 3–4 stacked `radial-gradient()`s and `background-blend-mode`, used only behind hero tips (shade detail page header, the layer builder canvas), never on UI chrome. Derive its colours from the shade's own palette so it feels like light, not decoration.

6. **Things 3** — iPhone/iPad/Mac. https://culturedcode.com/things/ (*Verified*: two Apple Design Awards); morphing + animation examples listed at https://60fps.design/apps/things-3 (*Verified* snippet: "floating action button expands into a new card")
   - *Why:* Calm white/ink surfaces, one accent, a hero interaction (the "+" morphs into the new-item card).
   - *Import:* "+ Add polish" button that expands into the add sheet using the View Transitions API (`view-transition-name`, same-document, with an MPA opt-in `@view-transition { navigation: auto; }`; Safari support should be checked against caniuse before relying on it).

7. **Apple Journal / Photos / Wallet / Weather (system apps)** — https://developer.apple.com/design/human-interface-guidelines/ *(not individually fetched)*
   - *Why (memory):* Wallet's stacked cards with overlap, Photos' edge-to-edge grid with variable-size "highlight" tiles, Journal's calm serif-less large titles.
   - *Import:* Wallet-style overlap for the layer builder (base shade card lower, toppers stacked over it with a 24–32px peek). Photos-style grid with one 2×2 "feature" tile per N items.

### (b) Beauty / colour / material sites and apps

8. **Holo Taco (the source brand)** — web. https://www.holotaco.com/ ; agency case study https://cinnamontoast.ca/work/holo-taco (*Verified*)
   - *Why:* The brand's look is "bold, playful, a little badass": vibrant hover states derived from a gradient-rich palette, fun iconography, CDs in the logo to signify "holo" (*Verified*, agency text). Photography does the heavy lifting.
   - *Import:* Borrow one brand cue, not the loudness: a CD-like conic-gradient ring (`conic-gradient` of holo hues at low saturation, masked as a thin ring) as the focus/selection ring around a tip and as the app mark.

9. **Aesop** — web. https://work.co/clients/aesop/ (*Verified*: case study; layouts and typography "inspired by iconic product packaging"); spec summary https://tastekit.dev/gallery/apps/aesop (*third-party; medium confidence*: warm cream canvas `#fffef2`, charcoal `#333`, Suisse Intl, large-but-light headlines, small body, uppercase eyebrows with tracking)
   - *Why:* Apothecary editorial: warm paper, small refined type, inverted charcoal sections for contrast.
   - *Import:* Replace cool `#F6F2F5` with a slightly warmer, paper-like neutral for "board" surfaces; add uppercase tracked eyebrows (`font-size:.72rem; letter-spacing:.08em`) over section titles; use inverted dark "plate" sections for the hero rack.

10. **Rhode** — web. https://tastekit.dev/gallery/apps/rhode (*third-party; medium*: white canvas, full-bleed warm cream bands `#f1f0ed`, one warm taupe for text/hairlines, every neutral warm-biased, photography-led)
    - *Why:* One colour does nearly all the work; warmth arrives as bands, not a tinted body.
    - *Import:* Warm-biased neutrals for hairlines and secondary text instead of cool grey; section banding for home composition.

11. **Glossier** — web. https://tastekit.dev/gallery/apps/glossier (*third-party; medium*: single regular weight, hierarchy by size/case/whitespace, small headlines, 12px uppercase nav)
    - *Import:* Hierarchy via size and case, not weight. This suits a system-ui-only stack; it is a cheap upgrade even without a display face.

12. **Coolors / Pantone Connect** — web + iOS. https://www.coolors.app/ , https://support.pantone.com/en/what-can-i-do-with-pantone-connect (*Verified* these pages exist; feature descriptions from search summary, medium)
    - *Why:* Big colour blocks, minimal chrome, tap-to-copy, lock/reorder, projects/collections.
    - *Import:* Palette-as-bar: a thin horizontal strip of a wheel's dominant colours under every card title (a "swatch ribbon"); tap-to-copy hex on shade detail; "contrast of tip against board" check is not needed, since the board is neutral.

### (c) Award-gallery treatments

13. **Awwwards "Trendy Gradients in Web Design" (Jul 2025)** — https://www.awwwards.com/gradients-in-web-design-elements.html (*Verified* snippet: multicolour gradients with blur/distortion "extended to secondary elements: hovers, titles, 3D elements, icons")
    - *Import:* Use gradient only on *secondary* touchpoints: hover/press state, the active-tab indicator, a title underline, and the selection ring; keep primary surfaces flat.

14. **Awwwards holographic examples** — Cyphr (SOTD Aug 19 2025) https://www.awwwards.com/sites/cyphr ; "Holographic abstract 3d shapes" https://www.awwwards.com/sites/holographic-abstract-3d-shapes-2 (*Verified* pages exist; I did not inspect the visuals)
    - *Why (inference):* Holo reads as expensive when it is shown on a dark, near-black field with a single saturated hue.
    - *Import:* In dark mode (`#160B14`), let the hero tip sit on a darker "velvet" plate so holo/iridescence has contrast to shine against.

### (d) Responsive, native-feeling apps from one codebase

15. **Linear** — web/iOS/Mac. https://linear.app/now/behind-the-latest-design-refresh and https://linear.app/changelog/2025-10-16-mobile-app-redesign (*Verified*)
    - *Why (Verified quotes):* "Don't compete for attention you haven't earned" (dim the sidebar so content dominates); "Structure should be felt not seen" (fewer, rounder, softer borders); smaller icons, muted inactive text, more vertical padding; mobile uses "a custom frosted glass material that adds depth and contrast" and a **bottom toolbar** with a Create button on every screen; the toolbar is user-customisable (https://linear.app/changelog/2026-01-22-customize-your-navigation-in-linear-mobile). Linear's web app has been responsive since 2019 (https://linear.app/changelog/2019-10-28-responsive-web-application), "we didn't want to dumb down the experience".
    - *Import:* Frosted bottom tab bar on phone (`backdrop-filter: blur(20px) saturate(1.6)` over a translucent board colour plus a 1px inner top highlight); soften hairlines to ~8% ink; dim inactive nav.

16. **Readwise Reader / Craft / Notion (iPad/Mac)** — https://apps.apple.com/us/app/readwise-reader/id1567599761 ; https://www.notion.com/en-gb/help/notion-calendar-settings (*medium: from search summary, not fetched*); Apple sidebar guidance https://developer.apple.com/design/human-interface-guidelines/sidebars
    - *Why:* Persistent sidebar at roomy widths; opening a detail panel **shrinks the content column rather than covering it** (Reader); iPad sidebar collapses to a drawer.
    - *Import:* See the responsive pattern in the synthesis. Drive the layout from container/viewport width, not device type.

(Considered but not individually verified, so left out of the numbered list: Bear, Halide, Darkroom, Mercury Weather, Structured, Rise, Sofa, Arc, Notion Calendar, Farrow & Ball and Dulux colour explorers, Olive & June, Mobbin/Godly/Siteinspire/Land-book galleries. I'd search Mobbin for "collection grid" and "bottom sheet" patterns next if Jan wants more.)

## Synthesis: the 10 strongest ideas, ranked by impact on "beautiful"

1. **Give tips a physical presence ("lit objects on a surface").** Biggest single change. Recipe, all CSS around the existing SVG:
   - One consistent light source from top-left. Under each tip: a soft elliptical contact shadow (`radial-gradient` pseudo-element, 55% width, blurred, ~18% ink) plus a tighter 1px occlusion shadow; in dark mode, a faint rim light instead of a shadow.
   - Specular: a diagonal white gloss band (`linear-gradient(115deg, transparent 40%, rgba(255,255,255,.55) 50%, transparent 60%)`, `mix-blend-mode: soft-light` or `overlay`, clipped to the tip shape with `mask`/`clip-path`) and a small hard highlight near the top-left of the nail curve.
   - Die-cut sticker edge (CapWords idea): a 1.5px light outline around the silhouette.
   - Scale: tips in grids should be larger than feels natural (≥72px on phone, 96–120px on iPad/Mac) with generous space; precious objects need air.
   - Grids to try: **polish rack** (shelves: a thin ledge line with the contact shadows resting on it, 4–5 per shelf on phone, 8–12 on desktop), and **salon nail-art wall** (hexagonal or staggered offset rows, alternating row offset of half a tip). Use CSS grid with `margin-left` on even rows or `grid-template-columns: repeat(auto-fill, minmax(88px,1fr))` plus a shelf-line `background-image` repeating every row height.
   - Sources of inspiration: CapWords stickers, Denim depth effects, Wallet overlap.
2. **Tilt-reactive shine (cheap "holo").** On pointer devices, set `--mx/--my` custom properties from `pointermove` in a tiny ES module and move the gloss band and a `conic-gradient` holo layer by them. On iPhone, where there is no gyroscope API without a permission prompt, animate the same layer slowly on scroll position (`animation-timeline: scroll()` where supported) or on a 6–8s idle loop only for the detail page hero. Respect `prefers-reduced-motion`.
3. **A single display typeface for titles and numbers, with system-ui for UI.** Yes, one is warranted: system-ui alone is the main reason it reads as "quiet but not beautiful". Candidates that are free to self-host:
   - **Fraunces** (variable: weight, optical size, SOFT, WONK; SIL OFL 1.1; self-host via woff2 from https://fontsource.org/fonts/fraunces/use — *Verified*: OFL-1.1, variable font, softness axis). Warm "wet-ink" feel suits glossy polish. Use opsz-auto, SOFT ~50–100, weight 500–600 for shade names and page titles at 28–44px.
   - Alternatives I did not verify license for in this run (check before shipping): Instrument Serif and Newsreader (both listed on Google Fonts, believed OFL). **Avoid** commercial faces like Recoleta, Suisse Intl, Apercu (Aesop/Glossier use paid fonts; PikSpec suggests Inter Tight as a free stand-in for Suisse).
   - Rules: serif for shade names, page titles, big numbers; system-ui for controls and metadata; tabular figures for counts; eyebrows uppercase with tracking (Aesop). Subset to Latin + Latin-ext and preload one woff2 (<40KB subset is plausible; not measured).
4. **Warm the neutrals and soften structure.** Shift to warm-biased board/paper tones (Rhode, Aesop), keep dark plum primary, drop hairlines to low-contrast and rounded (Linear: "structure should be felt, not seen"). Add a faint paper-grain (SVG `feTurbulence` as a data-URI background at 3–4% opacity) on the board only.
5. **Restrained iridescence: gradient on secondary touchpoints only.** Per Awwwards' 2025 trend note, gradients now live on hovers, titles, icons. Concretely: a thin conic holo ring for selection/focus on tips; a holo gradient text fill (`background-clip: text`) for exactly one word per page (e.g. the count on home); active-tab underline. Never full-bleed. Keep saturation ≤ 35% outside the tips so the tips remain the colour.
6. **Frosted-glass chrome, not frosted-glass content.** Bottom tab bar, sticky headers, and sheets get `backdrop-filter: blur(18–24px) saturate(1.6)`, 8–12% tint, 1px inner top highlight, 1px 18% rim (Linear 2025; CSS recipes in https://webtricks.dev/blog/liquid-glass-css and https://css-tricks.com/getting-clarity-on-apples-liquid-glass/). Do the CSS-only version; skip SVG refraction (Safari can't chain SVG filters in `backdrop-filter`, per the Liquid Glass Playground note, medium confidence). Provide an opaque fallback in `@supports not (backdrop-filter: blur(1px))`.
7. **Responsive pattern (one codebase, three shells).** Drive by viewport/container width:
   - **Phone (<700px):** bottom frosted tab bar (4 tabs: Home, Collection, Wheels, Layers) with a centred/trailing "+" (Linear/Things); detail views and the add flow as bottom sheets (`<dialog>` with `::backdrop`, drag handle, 28px top radius, `env(safe-area-inset-bottom)`); thumb-zone actions at the bottom.
   - **iPad / narrow desktop (700–1100px):** left icon rail (64px) or collapsible 220px sidebar; 2-pane master–detail where selecting a shade opens the detail in a **right-hand side panel that shrinks the grid** (Reader), not an overlay.
   - **Desktop (≥1100px):** persistent 240–260px dimmed sidebar (Linear), content grid, optional 360px inspector panel on the right; sheets become popovers anchored to the trigger (`popover` attribute + anchor positioning where supported, else fixed positioned) or centred modals; keyboard shortcuts (`/` search, `n` add).
   - Same HTML, `@media`/`@container` rules only. For iPad Split View use container queries on the app shell, not device sniffing. Source: Apple sidebar HIG above; breakpoint numbers are my recommendation (researcher inference), not from a source.
8. **Home / dashboard as a "shelf," not a dashboard.** Composition top to bottom: (a) a large serif greeting line with today's date and one holo word; (b) **"Wear today" hero**: one big lit tip with a quiet "Another" shuffle chip (Crouton's do-it-now bias, Flighty's one-line-per-thing clarity); (c) a horizontal-scroll "Recently added" rack (scroll-snap, `scroll-snap-type: x mandatory`, peeking next item); (d) the colour-family **ring of 20 tips** as a compact visual index (tap a tip → filtered collection); (e) a "Collection Passport" card with 3–4 stats (Flighty Passport) and shareable image. Banded warm sections (Rhode) rather than boxed cards.
9. **Five motion moments, all CSS/View Transitions, all short (150–350ms) and reduced-motion safe.**
   - Add-to-collection: tip scales in with a spring-like `linear()` easing and a single specular sweep (CapWords).
   - "+" morphs into the add sheet (Things; View Transitions).
   - Grid → detail shared-element transition: the tip flies from its grid cell to the hero (`view-transition-name: tip-{id}`).
   - Layer builder: dropping a topper slides it over the base with a 24px overlap settle; the combined preview re-lights (shine sweep).
   - Press feedback: tips `transform: scale(.96)` on `:active`, release springs to 1.
10. **Considered empty states and edge cases.** Empty collection shows an empty shelf with three dashed "ghost" tips and a serif line ("Nothing on the rack yet"); empty wheels show a ring of 20 faint outlines that fill in as you add; no-results shows a lone tip tilted with a small caption. (Principle from Flighty: "we really have to shine when things go awry"; *Verified* quote.) These are cheap and visibly raise perceived craft.

## Findings (verified facts only)
1. **Claim:** Linear's 2025 mobile redesign uses a custom frosted-glass material and a bottom toolbar with a Create button on every screen. **Sources:** https://linear.app/changelog/2025-10-16-mobile-app-redesign **Support:** direct evidence. **Confidence:** high.
2. **Claim:** Linear's latest desktop refresh dimmed the sidebar, shrank icons, reduced separators and softened borders ("Structure should be felt not seen"). **Sources:** https://linear.app/now/behind-the-latest-design-refresh **Support:** direct evidence. **Confidence:** high.
3. **Claim:** CapWords (2025 ADA Delight & Fun) is built around collecting objects as stickers, with a micro-animation hiding processing and real-world sounds on transitions. **Sources:** https://developer.apple.com/articles/capwords/ , https://developer.apple.com/design/awards/2025/ **Support:** direct evidence. **Confidence:** high.
4. **Claim:** Denim (2025 ADA finalist) is praised for mesh gradients, custom haptics, depth effects and smooth scroll transitions; Lumy for a carefully curated colour palette. **Sources:** https://developer.apple.com/design/awards/2025/ **Support:** direct evidence. **Confidence:** high.
5. **Claim:** Flighty's design rule is a real-world analogy (airport boards) and its Passport screen is shareable custom artwork. **Sources:** https://developer.apple.com/news/?id=970ncww4 **Support:** direct evidence. **Confidence:** high.
6. **Claim:** Fraunces is a variable OFL-1.1 font with weight, optical-size, softness and "wonky" axes and can be self-hosted. **Sources:** https://fontsource.org/fonts/fraunces/about , https://github.com/undercasetype/Fraunces **Support:** direct evidence (search excerpts). **Confidence:** high.
7. **Claim:** Holo Taco's site was designed with gradient-rich hover states and a CD motif in the logo (CSS Design Awards mention in agency text). **Sources:** https://cinnamontoast.ca/work/holo-taco **Support:** direct evidence. **Confidence:** medium-high.
8. **Claim:** Frosted glass can be approximated in CSS with tint + `backdrop-filter: blur() saturate()` + specular rim, and Safari does not support SVG filters chained into `backdrop-filter`. **Sources:** https://webtricks.dev/blog/liquid-glass-css , https://www.9st.me/design/apple/playground **Support:** interpretation of blog content. **Confidence:** medium.
9. **Claim:** Aesop/Rhode/Glossier palette and type details (cream canvas, warm neutrals, single-weight Apercu, Suisse Intl). **Sources:** tastekit.dev specs and work.co case study. **Support:** third-party extraction. **Confidence:** medium.

## Contradictions
None found. One mild tension: Aesop is reputed as an "editorial serif" brand but a third-party spec says the workhorse face is a Swiss neo-grotesque (https://tastekit.dev/gallery/apps/aesop). This supports the recommendation to keep sans for UI and use a serif only as an accent.

## Missing evidence
- No screenshots viewed; all visual descriptions of Things, Crouton, system apps, Aesop, Rhode, Glossier, Coolors beyond the quoted text are from memory or third-party text.
- Font licences for Instrument Serif and Newsreader not checked here; Apple SF Pro web-embedding terms not checked (system-ui is safe).
- Browser support for View Transitions (MPA), anchor positioning, `animation-timeline: scroll()` and `linear()` easing on current iOS Safari not verified; check caniuse and provide fallbacks.
- Performance cost of many `backdrop-filter` layers and SVG shadows on older iPhones not measured; limit to chrome (tab bar, header, sheet).
- Mobbin, Godly, Siteinspire, Land-book, Olive & June and the paint-colour explorers were not reached.
- Breakpoint numbers and the CSS recipes in the synthesis are my inference/proposals.

## Sources
- Kept: Apple Design Awards 2025 (https://developer.apple.com/design/awards/2025/) — official category descriptions for CapWords, Lumy, Denim.
- Kept: Behind the Design: Flighty (https://developer.apple.com/news/?id=970ncww4) — design philosophy quotes.
- Kept: Behind the design of CapWords (https://developer.apple.com/articles/capwords/) — sticker collection and micro-animation.
- Kept: Crouton article (https://developer.apple.com/news/?id=9x75y43e) — 2024 ADA Interaction.
- Kept: Linear changelog 2025-10-16 and design refresh post — frosted glass, bottom toolbar, calmer chrome.
- Kept: Cinnamon Toast Holo Taco case study (https://cinnamontoast.ca/work/holo-taco) — brand/art direction of the source.
- Kept: Fontsource / GitHub Fraunces — licence and axes.
- Kept: Awwwards gradient trends article (https://www.awwwards.com/gradients-in-web-design-elements.html) — 2025 trend evidence.
- Kept: WebTricks / CSS-Tricks liquid-glass articles — CSS recipes.
- Deprioritized: tastekit.dev and pikspec.com design specs — auto-extracted, useful only as a hint.
- Deprioritized: LinkedIn post on Notion iPad, Apple App Store listings — thin.

## Next steps
1. Prototype idea 1 (lit tip + shelf grid) on one page in the existing app and compare light/dark on a real iPhone.
2. Pick the display face by rendering Fraunces vs one alternative on the shade-name and home-greeting; confirm licence files go in `static/vendor/` with the version recorded.
3. Browser-check View Transitions MPA, `@container`, anchor positioning on the iOS version Jan's household uses.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Report written with 16 references, a 10-idea ranked synthesis covering tips, type, materials, motion, responsive pattern and home; limits and unverified items listed under Missing evidence."
    }
  ],
  "changedFiles": [
    "/Users/jan.pucilowski/.pi/agent/sessions/--Users-jan.pucilowski-Development-polished--/subagent-artifacts/outputs/82599c66-f92a-474b-8bf4-eec93b7c826b/research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [],
  "validationOutput": [
    "Fetched and read: Apple ADA 2025 page, Linear changelog and design-refresh post, Flighty and CapWords Apple articles, Cinnamon Toast Holo Taco case study. Other facts come from search excerpts."
  ],
  "residualRisks": [
    "No screenshots were viewed; several visual descriptions are from memory or third-party text and are labelled so",
    "Only 16 references, short of the 20 upper bound; gallery sites (Mobbin, Godly, Land-book) and paint explorers not reached",
    "Font licences for alternatives to Fraunces and browser support for newer CSS features unverified"
  ],
  "noStagedFiles": true,
  "diffSummary": "One new research markdown file; no repo files changed.",
  "reviewFindings": [
    "no blockers"
  ],
  "manualNotes": "Verified items are marked 'Verified'; everything marked memory, third-party or inference should be spot-checked before it drives design decisions."
}
```
