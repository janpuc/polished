import PolishedStore
import SwiftUI

/// Chips that wrap onto new lines, left to right.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    var lineSpacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(proposal.width ?? .infinity, subviews)
        let height = rows.last.map { $0.y + $0.height } ?? 0
        return CGSize(width: proposal.width ?? rows.map(\.width).max() ?? 0, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        for row in arrange(bounds.width, subviews) {
            var x = bounds.minX
            for index in row.indices {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(at: CGPoint(x: x, y: bounds.minY + row.y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
        }
    }

    private struct Row {
        var indices: [Int] = []
        var y: CGFloat = 0
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func arrange(_ maxWidth: CGFloat, _ subviews: Subviews) -> [Row] {
        var rows: [Row] = []
        var row = Row()
        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            if !row.indices.isEmpty, row.width + spacing + size.width > maxWidth {
                rows.append(row)
                row = Row(y: row.y + row.height + lineSpacing)
            }
            row.width += (row.indices.isEmpty ? 0 : spacing) + size.width
            row.height = max(row.height, size.height)
            row.indices.append(index)
        }
        if !row.indices.isEmpty { rows.append(row) }
        return rows
    }
}

/// A chip: Fill at rest, ink with Primary-on text when on (docs/advice v3 4.3, the level and
/// filter chips). At least 44 pt tall to tap.
struct Chip: View {
    let title: String
    let isOn: Bool
    let action: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(isOn ? Color.primaryOn : Color.ink)
                .padding(.horizontal, 14)
                .frame(minHeight: 36)
                .background(isOn ? Color.primaryFill : Color.fill, in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(ChipPressStyle(reduceMotion: reduceMotion))
        .accessibilityAddTraits(isOn ? .isSelected : [])
    }
}

private struct ChipPressStyle: ButtonStyle {
    let reduceMotion: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label.pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

extension View {
    /// A list row's background: Surface, and Fill2 while it is the selection of a split view's
    /// list column (the system's own selection fill would be the near-black tint).
    func rowSurface(_ route: Route, selection: Binding<Route?>?) -> some View {
        listRowBackground(selection?.wrappedValue == route ? Color.fill2 : Color.surface)
    }
}
