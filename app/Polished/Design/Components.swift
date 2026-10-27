import SwiftUI

/// The one filled action of a screen: Primary fill, 50 pt, radius 12, 17/600.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(Color.primaryOn)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Color.primaryFill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .opacity(isEnabled ? 1 : 0.4)
            .pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

/// The one filled action of a screen that cannot be undone (Delete wheel): Bad fill, white text.
struct DestructiveButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(Color.white)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Color.bad, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .opacity(isEnabled ? 1 : 0.4)
            .pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

/// Everything else that is a button: Fill with ink text, same size.
struct SecondaryButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(Color.ink)
            .frame(minHeight: 50)
            .padding(.horizontal, 16)
            .background(Color.fill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

/// A small secondary action inside a card: Fill capsule, 44 pt tall to tap, ink text.
struct CompactButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Color.ink)
            .padding(.horizontal, 14)
            .frame(minHeight: 40)
            .background(Color.fill, in: Capsule())
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

/// The filled action inside a hero card: Primary capsule, 44 pt tall to tap.
struct CompactPrimaryButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Color.primaryOn)
            .padding(.horizontal, 16)
            .frame(minHeight: 40)
            .background(Color.primaryFill, in: Capsule())
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .pressScale(configuration.isPressed, reduceMotion: reduceMotion)
    }
}

extension View {
    /// Press: scale 0.96 from the current value with a spring, so it can be interrupted
    /// (docs/NATIVE.md 5.7). Reduce Motion keeps an opacity change only.
    func pressScale(_ pressed: Bool, reduceMotion: Bool) -> some View {
        self
            .scaleEffect(pressed && !reduceMotion ? 0.96 : 1)
            .opacity(pressed && reduceMotion ? 0.7 : 1)
            .animation(reduceMotion ? .easeOut(duration: 0.15) : .snappy(duration: 0.2), value: pressed)
    }

    /// A group: Surface, radius 16, the 1 pt ring edge instead of a shadow.
    func groupCard() -> some View {
        self
            .background(Color.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .strokeBorder(Color.line, lineWidth: 1)
            }
    }
}

/// A section heading: the 22/600 section title, with an optional trailing link.
struct SectionHeading: View {
    let title: String
    var trailing: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .font(.title2.weight(.semibold))
                .foregroundStyle(Color.ink)
            Spacer()
            if let trailing {
                HStack(spacing: 4) {
                    Text(trailing)
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.bold))
                }
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.ink2)
            }
        }
        .accessibilityAddTraits(.isHeader)
    }
}

/// One line and one action, with the unpainted drawing where the thing will appear.
struct EmptyState: View {
    let line: String
    var action: String?
    var perform: () -> Void = {}

    var body: some View {
        VStack(spacing: 20) {
            TipView.unpainted(size: .l)
                .padding(.bottom, 8)
            Text(line)
                .font(.body)
                .foregroundStyle(Color.ink2)
                .multilineTextAlignment(.center)
            if let action {
                Button(action, action: perform)
                    .buttonStyle(PrimaryButtonStyle())
                    .frame(maxWidth: 280)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}
