import PolishedModels
import SwiftUI

/// The level as four segments, each with its arc and its word: a segmented control that can carry
/// the glyphs, which the system's cannot (docs/advice v3 4.1: "the edit sheet's segmented control
/// shows the same arc at 16 pt in each segment"). One of the four is always on.
struct LevelPicker: View {
    @Binding var state: BottleState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 4) {
            ForEach(BottleState.allCases, id: \.self) { level in
                let isOn = state == level
                Button {
                    state = level
                } label: {
                    HStack(spacing: 5) {
                        LevelArc(fraction: level.fraction, diameter: 16, arc: isOn ? Color.primaryOn : Color.ink)
                        Text(level.label)
                            .font(.subheadline.weight(.medium))
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                    }
                    .foregroundStyle(isOn ? Color.primaryOn : Color.ink)
                    .frame(maxWidth: .infinity, minHeight: 40)
                    .background(isOn ? Color.primaryFill : Color.clear, in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(level.label)
                .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
                .accessibilityIdentifier("level-\(level.rawValue)")
            }
        }
        .padding(3)
        .background(Color.fill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .animation(reduceMotion ? .easeOut(duration: 0.15) : .snappy(duration: 0.25), value: state)
        .sensoryFeedback(.selection, trigger: state)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Level")
    }
}
