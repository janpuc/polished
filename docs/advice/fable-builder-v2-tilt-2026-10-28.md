# Builder v2 and the tilt light

Fable (claude-fable-5-1), 2026-10-28, from Jan's first on-device feedback on the TestFlight build: the edited slot should be easier to identify, too many per-layer controls, 2 coats by default is not great, wiggle mode to reorder, matte didn't apply, and the missing tilt shimmer.


## A. Builder v2

**Interaction model.** The sheet opens at `.medium`, not `.large`, so the ring stays in view while the stack grows. Focusing the search field or scrolling the list sets the detent to `.large` through the existing `$detent` binding passed down as a `Binding<PresentationDetent>`. Adding a layer never changes the detent. iPad keeps the inspector at 360 to 400 pt with the same content. Duo stays as built, inspector when unfolded, sheet when folded; the `ArrangementView` split remains run-6 debt.

**Identifying the edited slot on the ring** (`WheelRing`, new inputs `editing: Int?`, `editingRecipe: TipRecipe?`):

1. The slot lifts: `scaleEffect(1.12)` and an outward `offset` of 6 pt along its radius, `zIndex(1)`, `.snappy(duration: 0.25)`. The 2 pt ink ring stays. No foil.
2. The other slots dim to `opacity(0.55)`, `.smooth(duration: 0.3)`. The Swatches list below is untouched.
3. The hub swaps to the slot: `DisplayNumber` shows the position with caption "slot", `contentTransition(.numericText())`. It returns to the count on close. The sheet title "Slot 11" and the hub now say the same thing.
4. The live composite paints in the slot. `WheelScreen` reads `builder?.model.sheet?.tip` and passes it as `editingRecipe`; the slot draws it instead of the tile's own recipe with the same `.id(recipe)` crossfade the head uses. An empty draft shows the unpainted tip and number. On save the sweep runs as today.

Reduce Motion: no lift, dim and hub swap only.

**Layer rows.** One row per layer, 52 pt tall, in the existing `groupCard` on the 2 pt rail:

```
│ ▐▓▌  One-Coat Black                      │
│ ▐▓▌  Flakie Holo Taco              ×2    │
```

- Leading `TipView(size: .s)`, name in `.headline`, `lineLimit(1)`, `truncationMode(.middle)`. The Base/Top caption goes; the rail and order say it. The row label for VoiceOver keeps it: "Top, Flakie Holo Taco, 2 coats".
- A `×2` badge in `.footnote` `monospacedDigit` on a `Fill` capsule, only when coats > 1. Default coats is 1 from the server, so a new stack shows no badges.
- Tap the row: `.popover` anchored to the row with `presentationCompactAdaptation(.popover)` so it stays a popover on iPhone, 260 pt wide. Contents: `Stepper("Coats", value:, in: 1...5)` with the number in `.numericText`, a `Divider`, `Button("Remove", role: .destructive)`. Each step calls `model.changeCoats`, which already applies optimistically.
- The −/+, ↑/↓ and × buttons are removed. Up and down survive as `accessibilityAction(named: "Move up")` and `"Move down"`, plus `accessibilityAdjustableAction` for coats and a "Remove" action.
- No swipe-to-delete: the rows are not in a `List`, and the long press is taken by arranging. Remove is one tap away in the popover.

**Wiggle to reorder** (new `ArrangeStack` state in `BuilderView`):

- Gesture per row: `LongPressGesture(minimumDuration: 0.35).sequenced(before: DragGesture(minimumDistance: 0, coordinateSpace: .named("stack")))`. Long press success sets `arranging = true`, fires `.selection`, lifts the row (`scaleEffect(1.04)`, shadow 8/16 `ShadowInk` 20%). While arranging, a plain drag on any row picks it up, no second long press.
- Jiggle: a `TimelineView(.animation(minimumInterval: 1/60, paused: !arranging))` around the card; row `i` gets `rotationEffect(.degrees(1.5 * sin(2π · 7 · t + 1.3 · i)))` and a ±0.5 pt `offset(y:)`. The dragged row does not jiggle.
- Drag: the lifted row follows the finger 1:1 by `offset(y: translation.height)` from where it was grabbed. Target index = `clamp(from + Int((translation.height / rowHeight).rounded()))`. Other rows reflow by `offset(y: ±rowHeight)` under `.spring(response: 0.3, dampingFraction: 1)`; a reflow crossing fires `.selection`. No `matchedGeometryEffect` is needed.
- Drop: `.impact(weight: .medium)`, the row settles with `.spring(response: 0.35, dampingFraction: 0.85)`. The model gets `abs(to − from)` calls of `model.move(layer, up:)` in order; the queue keeps them sequential and the server API stays unchanged.
- Exit: a "Done" pill, `CompactPrimaryButtonStyle`, at the top right of the layers card, or a tap outside the card. Arranging also ends on save, cancel and sheet dismissal.
- Reduce Motion: no jiggle and no lift scale; each row shows a trailing `line.3.horizontal` handle while arranging and the drag still works.
- Haptics map gains "Layer picked up: `.selection`; layer dropped: `.impact(.medium)`".

**iPhone, `.medium` (390 pt):**
```
━━
▐▓▓▓▌ Slot 11                  Cancel   Save swatch
▐▓▓▓▌ Holos · One-Coat Black + Flakie Holo Taco ×2
┌─────────────────────────────────────┐
│ ▐▓▌ One-Coat Black                  │
│ ▐▓▌ Flakie Holo Taco           ×2   │
└─────────────────────────────────────┘
[Over black] [Copy from…] [Same as last]
[ ⌕ Search shades                 ] [▣]   ← focus pulls .large
```
The ring behind shows slot 11 lifted with the composite, the rest dimmed, the hub reading "11 slot".

**iPhone, `.large`:** the same head and card, then the scope control, the results, "Name and note", "Painted on", Remove swatch. While arranging, the card reads:
```
┌ Layers                         (Done) ┐
│ ▐▓▌ One-Coat Black        ≡  (jiggle) │
│ ▐▓▌ Flakie Holo Taco  ×2  ≡  (jiggle) │
└───────────────────────────────────────┘
```

## B. Tilt light

§4.4 stands with these refinements.

**Core Motion.** `CMMotionManager`, `deviceMotionUpdateInterval = 1/30`, `.xArbitraryZVertical`, delivered to the main queue. Capture a reference attitude on start and whenever `scenePhase` becomes `.active`; relative attitude via `attitude.multiply(byInverseOf: reference)`. Let the reference drift toward the current attitude with a 4 s time constant so a changed grip recentres and the light never sticks at the clamp. Clamp roll and pitch to ±20°, low-pass with α 0.18, map `lx = −0.35 + roll/20° · 0.6`, `ly = −0.55 + pitch/20° · 0.4`. Keep the mapping as a pure `TipLightMapper` so it has unit tests. Updates run only while at least one `.live` view is on screen, counted by `onAppear`/`onDisappear`.

**Gating,** all freezing at `TipLight.static`: Reduce Motion, Low Power Mode (observe the power-state notification), `thermalState >= .serious`, `scenePhase != .active`, no `isDeviceMotionAvailable`, the simulator. A Debug launch argument `-light lx,ly` pins the light for screenshots.

**Where.** Home hero, shade-detail hero, rack, builder head, ring slots including the lifted editing slot. Not list rows, picker rows, mini rings or widgets.

**Two steps, same run.** Step 1 drives the existing `TipSurfaceLight` from the model, since its pool already takes `lx, ly`. That is tilt with zero shader risk. Step 2 adds `TipLight.metal`, applied with `.layerEffect(ShaderLibrary.tipLight(.float2(size), .float2(light), .float(spec), .float(holo), .float(gloss)), maxSampleOffset: .zero)` on the painted canvas only, inside the clip, never on chrome. When live, the Canvas pool alpha drops to 0 so the pool is not drawn twice.

```metal
[[stitchable]] half4 tipLight(float2 pos, SwiftUI::Layer layer,
    float2 size, float2 light, float spec, float holo, float gloss) {
  half4 c = layer.sample(pos);            // premultiplied
  float2 uv = pos / size;
  float2 p = float2(0.5 + 0.4*light.x, 0.5 + 0.4*light.y);
  float2 d = (uv - p) / float2(0.30, 0.20);   // 60% by 40% ellipse
  float pool = spec * exp(-1.6 * dot(d, d));
  const float th = 115.0 * M_PI_F / 180.0;
  float t = uv.x * cos(th) + uv.y * sin(th);
  float centre = 0.5 + 0.3 * light.x;
  float w = 1.0 - smoothstep(0.0, 0.14, abs(t - centre));
  float hue = fract(0.9 * t + 0.35 * light.x + 0.15 * light.y);
  half3 rainbow = half3(hsv2rgb(float3(hue, 0.75, 1.0)));
  half3 add = half(pool) * (c.a - c.rgb)                      // screen white
            + half(holo * w * gloss) * rainbow * (c.a - c.rgb); // screen rainbow
  return half4(c.rgb + add, c.a);
}
```

Strengths come from the recipe's visible layers, from the last opaque one upward: `spec` from the top non-clear layer, 0.35 creme and jelly, 0.6 metallic, chrome and reflective, 0.45 glitter, 0 matte; `holo` is the sum of 0.22 holographic, 0.14 iridescent, 0.10 flakie, toppers ×0.6, clamped to 0.3; `gloss` 0 when the top layer is matte, else 1. Matte therefore returns the sample unchanged.

**Budget.** Instruments on an iPhone 18 Pro with the 20-slot ring and the hero live while tilting: Core Animation FPS ≥ 110, main thread < 15%, GPU < 3 ms a frame. If the ring misses, it falls back to `.static` and the heroes stay live.

**Delight.** The shade-detail hero's holo band sweeps across the nail as the phone tilts, strongest on holographic shades. On the ring, each slot's light is already turned by its angle, so a tilt sends the highlight travelling around the wheel like a real one turned under a lamp.

## C. Staged plan

**Run 1: builder v2, plus P-code removal in the app** (other brief). Files: `BuilderView`, `BuilderParts` (new `LayerRow`, `LayerPopover`, `ArrangeStack`), `BuilderPresentation` (detent binding), `WheelRing`, `WheelScreen`, `docs/NATIVE.md` §5.2, 5.3, 5.7, 5.8. Acceptance in the simulator:

- `BuilderFlow` opens slot 11: screenshot shows the sheet at `.medium`, the ring visible, slot 11 lifted, the hub reading 11. XCUITest asserts the hub's label and the sheet's "Slot 11".
- After `pick-<id>`: the ring slot's accessibility label contains the shade; screenshot 05 shows the composite in the slot.
- Tap the layer row: popover with "Coats" stepper; increment; badge "×2" appears; summary updates.
- `row.press(forDuration: 0.6, thenDragTo: otherRow)`: order swaps, "Done" exists, then disappears after tapping it. Summary reflects the new order.
- Reduce Motion run of the flow (`-reducemotion` launch argument through `UIAccessibility` override not available, so inject through an environment override in `-uitest`): handles visible, no lift.
- `app.performAccessibilityAudit()` passes on the builder; the row exposes Move up, Move down, Remove.
- Flows green on iPhone 18 Pro, iPad Pro 13", Duo, light and dark.

**Run 2: tilt light and the Wear today widget.** Files: `TipLightModel`, `TipLightMapper`, `LightGate`, `TipLight.metal`, `TipView` (`light: .live`), `docs/NATIVE.md` §4.4, the widget's App Group snapshot. Acceptance:

- Swift Testing: mapper vectors at 0°, ±20°, ±40° clamp; gate truth table; strength table per fixture case.
- The gallery screen renders twelve recipes at three pinned lights into the report; a matte case is byte-identical across lights.
- `xcodebuild` compiles the shader; the parity montage at the default light stays within the run-1 tolerance.
- Flows unchanged and green; the simulator shows the static light.

**On-device checklist for Jan** (iPhone, then iPad):
1. Open a slot at `.medium`: can you tell which slot without reading the sheet?
2. Add three layers by tapping: the slot on the ring repaints each time.
3. Tap a row, step coats to 3, see "×3"; remove a layer from the popover.
4. Long press a row: jiggle, drag to the top, Done. Then with Reduce Motion on: handles, no jiggle, drag still works.
5. Shade detail of a holographic shade: tilt left and right; the band should move within a frame, no lag, and settle without drift after ten seconds.
6. The wheel page: tilt and watch the highlight travel around the ring; check the battery and warmth after two minutes.
7. Low Power Mode on: the light freezes; off: it resumes.

**Need from main agent:** none blocking. Two choices to confirm with Jan when the run is reported, not before it starts: the sheet opening at `.medium`, and the hub swapping to the slot number while editing.
