import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The colour of a shade's nail tip, when the photos gave the wrong one: a system `ColorPicker`
/// sets it for the household, Reset goes back to the colour read from the photos. The server
/// keeps it across syncs (docs/NATIVE.md 1, "Tip colour override"). Not optimistic: the tip above
/// changes when the server has answered.
struct TipColourSection: View {
    let detail: Resource<ShadeDetail>
    let value: ShadeDetail
    @Environment(AppModel.self) private var app
    @State private var expanded = false
    @State private var color = Color.gray
    @State private var hexText = ""
    @State private var hexError: String?
    @State private var save = SaveAction()

    private var currentHex: String { value.shade.tip.hex.lowercased() }
    private var isOverride: Bool { value.tipSource == "override" }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            DisclosureGroup(isExpanded: $expanded) {
                VStack(alignment: .leading, spacing: 0) {
                    ColorPicker("Pick a colour", selection: $color, supportsOpacity: false)
                        .foregroundStyle(Color.ink)
                        .padding(.horizontal, 16)
                        .frame(minHeight: 52)
                        .accessibilityIdentifier("tip-colour-picker")
                    Divider().padding(.leading, 16)
                    HStack {
                        Text("Hex").foregroundStyle(Color.ink)
                        Spacer(minLength: 12)
                        TextField("#a647d1", text: $hexText)
                            .font(.body.monospaced())
                            .multilineTextAlignment(.trailing)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.done)
                            .frame(maxWidth: 130)
                            .onSubmit { Task { await applyTyped() } }
                            // A colour is replaced, not edited: starting to type selects it all.
                            .onReceive(NotificationCenter.default.publisher(for: UITextField.textDidBeginEditingNotification)) {
                                guard let field = $0.object as? UITextField, field.accessibilityIdentifier == "tip-colour-hex" else { return }
                                DispatchQueue.main.async { field.selectAll(nil) }
                            }
                            .accessibilityLabel("Tip colour as hex")
                            .accessibilityIdentifier("tip-colour-hex")
                    }
                    .padding(.horizontal, 16)
                    .frame(minHeight: 52)
                    Divider().padding(.leading, 16)
                    HStack {
                        Text(sourceLine)
                            .font(.footnote)
                            .foregroundStyle(Color.ink2)
                        Spacer(minLength: 12)
                        Button("Reset") { Task { await apply(nil) } }
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Color.ink)
                            .disabled(!isOverride || save.isRunning)
                            .frame(minHeight: 44)
                            .accessibilityIdentifier("tip-colour-reset")
                    }
                    .padding(.horizontal, 16)
                    if let message = hexError ?? save.generalError ?? save.fieldErrors["hex"] {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(Color.bad)
                            .padding(.horizontal, 16)
                            .padding(.bottom, 10)
                    }
                }
                .groupCard()
                .padding(.top, 12)
            } label: {
                SectionHeading(title: "Tip colour")
            }
        }
        .onAppear {
            color = Color(hex: currentHex)
            hexText = currentHex
        }
        .onChange(of: currentHex) {
            color = Color(hex: currentHex)
            hexText = currentHex
        }
        // The picker reports every drag; the server hears of the colour a moment after the last.
        .task(id: color) {
            let hex = Self.hex(of: color)
            guard hex != currentHex else { return }
            try? await Task.sleep(for: .milliseconds(700))
            guard !Task.isCancelled else { return }
            await apply(hex)
        }
    }

    private var sourceLine: String {
        switch value.tipSource {
        case "override": "Set by you"
        case "sampled": "Read from the photos"
        default: "No colour read yet"
        }
    }

    /// A colour typed as `#rrggbb` (the `#` is optional); a wrong one says so without asking the server.
    private func applyTyped() async {
        var typed = hexText.trimmingCharacters(in: .whitespaces).lowercased()
        if !typed.hasPrefix("#") { typed = "#" + typed }
        guard typed.count == 7, typed.dropFirst().allSatisfy(\.isHexDigit) else {
            hexError = "Use a colour like #7a3fd1."
            return
        }
        hexError = nil
        guard typed != currentHex else { return }
        await apply(typed)
    }

    private func apply(_ hex: String?) async {
        hexError = nil
        guard
            let updated = await save.run({
                try await app.writes.perform(.setTipColour(shadeID: value.shade.id, hex: hex), affecting: .tipColour)
            })
        else { return }
        detail.set(updated)
    }

    /// `#rrggbb` in sRGB, lowercase.
    static func hex(of color: Color) -> String {
        let resolved = UIColor(color)
        var red: CGFloat = 0, green: CGFloat = 0, blue: CGFloat = 0, alpha: CGFloat = 0
        resolved.getRed(&red, green: &green, blue: &blue, alpha: &alpha)
        func byte(_ value: CGFloat) -> Int { max(0, min(255, Int((value * 255).rounded()))) }
        return String(format: "#%02x%02x%02x", byte(red), byte(green), byte(blue))
    }
}
