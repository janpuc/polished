import SwiftUI

/// Fraunces, the four display roles only (docs/NATIVE.md 5.5): the greeting, a shade's title, a
/// wheel's name and the hub and collection numbers. Never below 22 pt, never in rows, buttons,
/// labels, chips or tabs; those are SF through the system text styles.
enum DisplayRole {
    case greeting
    case shadeTitle
    case wheelNameCard
    case wheelNamePage
    case hubNumber
    case collectionNumber

    static let postScriptName = "Fraunces144pt-SemiBold"

    func size(regular: Bool) -> CGFloat {
        switch self {
        case .greeting: regular ? 40 : 34
        case .shadeTitle: 28
        case .wheelNameCard: 22
        case .wheelNamePage: 34
        case .hubNumber: 56
        case .collectionNumber: 28
        }
    }

    var textStyle: Font.TextStyle {
        switch self {
        case .greeting, .wheelNamePage, .hubNumber: .largeTitle
        case .shadeTitle, .collectionNumber: .title
        case .wheelNameCard: .title2
        }
    }
}

extension View {
    /// Sets a display role's font; Dynamic Type scales it with its text style up to ×1.35
    /// (xxxLarge), so the greeting holds one line.
    func displayFont(_ role: DisplayRole) -> some View {
        modifier(DisplayFontModifier(role: role))
    }
}

private struct DisplayFontModifier: ViewModifier {
    let role: DisplayRole
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    func body(content: Content) -> some View {
        content
            .font(.custom(DisplayRole.postScriptName, size: role.size(regular: horizontalSizeClass == .regular), relativeTo: role.textStyle))
            .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
    }
}

/// A number in Fraunces. The static cut has no tabular figures (`VERSIONS.txt`), so each digit
/// sits in a cell as wide as the widest digit and a count does not jitter as it changes.
struct DisplayNumber: View {
    let value: Int
    let role: DisplayRole

    var body: some View {
        Digits(value: value, role: role)
            .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(String(value))
    }

    private struct Digits: View {
        let value: Int
        let role: DisplayRole
        @Environment(\.horizontalSizeClass) private var horizontalSizeClass
        @ScaledMetric private var typeScale: CGFloat

        /// The widest digit advance (the 0) in em: 1226 of 2000 units.
        private static let cellEm = 0.613

        init(value: Int, role: DisplayRole) {
            self.value = value
            self.role = role
            _typeScale = ScaledMetric(wrappedValue: 1, relativeTo: role.textStyle)
        }

        var body: some View {
            let cell = role.size(regular: horizontalSizeClass == .regular) * typeScale * Self.cellEm
            HStack(spacing: 0) {
                ForEach(Array(String(value).enumerated()), id: \.offset) { _, digit in
                    Text(String(digit))
                        .displayFont(role)
                        .frame(width: cell)
                }
            }
        }
    }
}
