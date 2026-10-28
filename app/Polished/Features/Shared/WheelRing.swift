import NailTips
import PolishedModels
import SwiftUI

/// The ring of a wheel: real painted tips on their hairline ring, slot 1 at twelve o'clock and the
/// numbers running clockwise (the web's `.ring`). A filled slot shows its stack's painted tip, an
/// empty one the plain Fill tip with its number, a draft the same with a dashed die-cut edge. Every
/// slot is a button that opens the builder.
/// The hub is the count in Fraunces over "of 20"; while the builder is open it is the slot's number
/// over "slot". The slot being edited lifts out of the ring, the others dim, and the slot paints
/// the draft as it grows (docs/NATIVE.md 5.2). Tips are decoration: each slot is a button that
/// says what it holds.
struct WheelRing: View {
    let tiles: [Tile]
    let slotCount: Int
    let filled: Int
    /// The slot to ring in foil (`?hl`, from Swatched on).
    var highlighted: Int?
    /// The slot the builder is open on: a plain ink ring, lifted 6 pt out of the ring and scaled
    /// to 1.12, the other slots dimmed, the hub reading its number.
    var editing: Int?
    /// What the draft in that slot looks like now; nil is an empty draft. Only read once
    /// `editingSummary` is set, so a draft that is still opening shows the slot as it was.
    var editingRecipe: TipRecipe?
    /// The draft's layers as a sentence ("" for an empty draft), nil until the draft is open.
    var editingSummary: String?
    /// A slot that was just saved and the serial of the save: one band of light crosses its tip.
    var sweeping: (position: Int, serial: Int)?
    var onSelect: ((Tile) -> Void)?

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion

    private var reduceMotion: Bool { systemReduceMotion || LaunchOptions.current.reduceMotion }

    /// 62 pt tips on a phone, 72 on a regular width; the radius 150 gives way to the screen.
    private var slotHeight: CGFloat { horizontalSizeClass == .regular ? 72 : 62 }

    var body: some View {
        GeometryReader { proxy in
            let radius = min(150, (min(proxy.size.width, proxy.size.height) - slotHeight) / 2)
            let geometry = RingGeometry(slotCount: slotCount, radius: radius, slotHeight: slotHeight)
            ZStack {
                // The plastic ring of a real wheel: a hairline through the lower part of the tips.
                Circle()
                    .stroke(Color.line2, lineWidth: 1.5)
                    .frame(width: 2 * (radius - 22), height: 2 * (radius - 22))
                ForEach(tiles) { tile in
                    slot(tile, geometry)
                }
                hub
            }
            .frame(width: proxy.size.width, height: proxy.size.height)
        }
        .aspectRatio(1, contentMode: .fit)
        .frame(maxWidth: 150 * 2 + slotHeight)
        .accessibilityElement(children: .contain)
    }

    private func slot(_ tile: Tile, _ geometry: RingGeometry) -> some View {
        let offset = geometry.offset(for: tile.position)
        let angle = geometry.angle(for: tile.position)
        let light = geometry.light(for: tile.position, screen: (TipLight.static.lx, TipLight.static.ly))
        let size = CGSize(width: geometry.slotWidth, height: geometry.slotHeight)
        let isEditing = editing == tile.position
        // The draft stands in for the slot once it is open.
        let draft = isEditing && editingSummary != nil
        let recipe = draft ? editingRecipe : (tile.filled ? TipRecipe(tips: tile.layerTips) : nil)
        let lift: Double = isEditing && !reduceMotion ? 6 : 0
        return Button {
            onSelect?(tile)
        } label: {
            ZStack {
                if highlighted == tile.position {
                    TipShape()
                        .fill(AngularGradient(colors: Foil.colors, center: .center))
                        .frame(width: size.width + 6, height: size.height + 6)
                }
                if editing == tile.position {
                    TipShape()
                        .stroke(Color.ink, lineWidth: 2)
                        .frame(width: size.width + 7, height: size.height + 7)
                }
                ZStack {
                    TipView(
                        recipe, size: .ring, dimensions: size, light: TipLight(lx: light.x, ly: light.y))
                        .id(recipe)
                        .transition(.opacity)
                }
                .animation(.smooth(duration: reduceMotion ? 0.15 : 0.3), value: recipe)
                .sweep(trigger: sweeping?.position == tile.position ? sweeping?.serial ?? 0 : 0)
                if tile.hasDraft && !tile.filled && !draft {
                    TipShape()
                        .stroke(Color.ink2, style: StrokeStyle(lineWidth: 1.5, dash: [3, 3]))
                        .frame(width: size.width, height: size.height)
                }
            }
            .rotationEffect(.radians(angle))
            .overlay {
                if recipe == nil && !dynamicTypeIsAccessibility {
                    Text("\(tile.position)")
                        .font(.caption.weight(.semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.ink2)
                }
            }
            .frame(width: max(size.width, 44), height: max(size.height, 44))
            .contentShape(Rectangle())
        }
        .buttonStyle(RingSlotStyle())
        .scaleEffect(isEditing && !reduceMotion ? 1.12 : 1)
        .offset(x: offset.x + lift * sin(angle), y: offset.y - lift * cos(angle))
        .opacity(editing != nil && !isEditing ? 0.55 : 1)
        .zIndex(isEditing ? 1 : 0)
        .animation(reduceMotion ? .easeOut(duration: 0.15) : .snappy(duration: 0.25), value: editing)
        .accessibilityLabel(label(tile, draft: draft ? editingSummary : nil))
        .accessibilityAddTraits(.isButton)
    }

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    private var dynamicTypeIsAccessibility: Bool { dynamicTypeSize.isAccessibilitySize }

    private func label(_ tile: Tile, draft: String?) -> String {
        if let draft {
            return draft.isEmpty ? "Slot \(tile.position), editing, nothing painted yet" : "Slot \(tile.position), editing, \(draft)"
        }
        if tile.filled {
            let painted = Words.day(tile.paintedOn).map { ", painted \($0)" } ?? ""
            let swatched = highlighted == tile.position ? ", swatched here" : ""
            return "Slot \(tile.position), \(tile.summary)\(painted)\(swatched)"
        }
        return tile.hasDraft ? "Slot \(tile.position), draft in progress" : "Slot \(tile.position), empty"
    }

    private var hub: some View {
        VStack(spacing: 0) {
            DisplayNumber(value: editing ?? filled, role: .hubNumber)
                .foregroundStyle(Color.ink)
            Text(editing == nil ? "of \(slotCount)" : "slot")
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
        }
        .contentTransition(.numericText())
        .animation(.smooth(duration: reduceMotion ? 0.15 : 0.3), value: editing)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(editing.map { "Editing slot \($0)" } ?? "\(filled) of \(slotCount) slots filled")
        .accessibilityIdentifier("wheel-hub")
    }
}

/// Slot press: lifts to 1.08 for a moment (docs/NATIVE.md 5.7, moment 5).
private struct RingSlotStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? 1.08 : 1)
            .animation(.snappy(duration: 0.15), value: configuration.isPressed)
    }
}

/// The foil, used for the highlighted slot only (docs/advice v3 2.6).
enum Foil {
    static let colors: [Color] = [
        Color(red: 1, green: 0.37, blue: 0.66), Color(red: 1, green: 0.70, blue: 0.28),
        Color(red: 0.97, green: 0.94, blue: 0.42), Color(red: 0.31, green: 0.91, blue: 0.64),
        Color(red: 0.25, green: 0.77, blue: 1), Color(red: 0.56, green: 0.48, blue: 1),
        Color(red: 1, green: 0.37, blue: 0.66),
    ]
}

/// The same ring at a small size, tips only, nothing to tap: a wheel's card in the list and on
/// Home. The tips keep their edge; the numbers and the hub are left out.
struct MiniRing: View {
    let tiles: [Tile]
    let slotCount: Int
    var diameter: CGFloat = 72

    var body: some View {
        let slotHeight = diameter * 0.21
        let radius = (diameter - slotHeight) / 2
        let geometry = RingGeometry(slotCount: slotCount, radius: radius, slotHeight: slotHeight)
        ZStack {
            Circle()
                .stroke(Color.line2, lineWidth: diameter > 100 ? 1 : 0.75)
                .frame(width: 2 * (radius - slotHeight * 0.35), height: 2 * (radius - slotHeight * 0.35))
            ForEach(tiles) { tile in
                let offset = geometry.offset(for: tile.position)
                let light = geometry.light(for: tile.position, screen: (TipLight.static.lx, TipLight.static.ly))
                TipView(
                    tile.filled ? TipRecipe(tips: tile.layerTips) : nil, size: .ring,
                    dimensions: CGSize(width: geometry.slotWidth, height: slotHeight),
                    light: TipLight(lx: light.x, ly: light.y)
                )
                .rotationEffect(.radians(geometry.angle(for: tile.position)))
                .offset(x: offset.x, y: offset.y)
            }
        }
        .frame(width: diameter, height: diameter)
        .accessibilityHidden(true)
    }
}
