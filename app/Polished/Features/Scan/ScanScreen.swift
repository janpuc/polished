import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// What a scan is for: a bottle for the collection (Add bottle), or a shade for the swatch being
/// built (the builder's scan button, which paints the shade as the next layer).
enum ScanPurpose {
    case bottle
    case layer((ShadeRow) -> Void)

    var actionTitle: String {
        switch self {
        case .bottle: "Add bottle"
        case .layer: "Add layer"
        }
    }

    var isLayer: Bool {
        if case .layer = self { true } else { false }
    }
}

/// The scan screen (docs/NATIVE.md 5.2, 5.3): the live camera with a framing guide, a torch and
/// Close, the typed field under it, and a card for what was found. Where the camera is missing
/// (a simulator, no access) the field stands alone with a line saying why.
struct ScanScreen: View {
    let purpose: ScanPurpose
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.openURL) private var openURL
    @State private var scan: ScanModel?
    @State private var text = ""
    @State private var torchIsOn = false
    @State private var camera = CameraAvailability.current
    @State private var flash = false
    @FocusState private var fieldFocused: Bool

    var body: some View {
        NavigationStack {
            Group {
                if let scan {
                    screen(scan)
                } else {
                    Color.board
                }
            }
            .background(Color.board)
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: ScanDestination.self) { _ in LearnedCodesScreen() }
        }
        .task {
            if scan == nil { scan = ScanModel(api: app.api, writes: app.writes) }
        }
    }

    private func screen(_ scan: ScanModel) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 32) {
                        VStack(alignment: .leading, spacing: 16) { viewfinder(scan); entry(scan) }
                            .frame(width: 480)
                        VStack(alignment: .leading, spacing: 16) { card(scan); learnedLink }
                            .frame(maxWidth: .infinity, alignment: .topLeading)
                    }
                    .frame(minWidth: 1000)
                    VStack(alignment: .leading, spacing: 16) {
                        viewfinder(scan)
                        entry(scan)
                        card(scan)
                        learnedLink
                    }
                    .frame(maxWidth: 520)
                    .frame(maxWidth: .infinity)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: scan.phase) {
                guard scan.phase != .idle else { return }
                withAnimation(.smooth) { proxy.scrollTo("scan-card", anchor: .top) }
            }
        }
        .task(id: text) {
            // The card follows the field a moment after the last key, as the web's does.
            if !text.isEmpty { try? await Task.sleep(for: .milliseconds(300)) }
            guard !Task.isCancelled else { return }
            await scan.lookup(typed: text)
        }
        .sensoryFeedback(.impact(flexibility: .rigid), trigger: scan.recognitions)
        .sensoryFeedback(.warning, trigger: scan.warnings)
        .onChange(of: scan.recognitions) {
            flash = true
            Task {
                try? await Task.sleep(for: .milliseconds(450))
                flash = false
            }
        }
    }

    // MARK: Camera

    private func viewfinder(_ scan: ScanModel) -> some View {
        ZStack {
            switch camera {
            case .ready:
                DataScannerView(torchIsOn: $torchIsOn) { barcode in
                    Task { await scan.recognise(barcode: barcode) }
                }
                .accessibilityLabel("Camera")
                framingGuide
            case .unsupported, .denied:
                unavailable
            }
            VStack {
                HStack {
                    if camera == .ready, DataScannerView.hasTorch { torchButton }
                    Spacer()
                    closeButton
                }
                Spacer()
            }
            .padding(12)
        }
        .frame(maxWidth: .infinity)
        .aspectRatio(camera == .ready ? 3.0 / 4.0 : 16.0 / 9.0, contentMode: .fit)
        .background(camera == .ready ? Color.black : Color.fill)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .accessibilityElement(children: .contain)
    }

    /// The box to hold the barcode in; it lights up on the frame a code is accepted.
    private var framingGuide: some View {
        RoundedRectangle(cornerRadius: 16, style: .continuous)
            .strokeBorder(flash ? Color.ok : Color.white.opacity(0.85), lineWidth: flash ? 4 : 2)
            .frame(maxWidth: 280, maxHeight: 150)
            .scaleEffect(flash ? 1.04 : 1)
            .animation(.snappy(duration: 0.2), value: flash)
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }

    private var unavailable: some View {
        VStack(spacing: 10) {
            Image(systemName: camera == .denied ? "camera.fill" : "barcode.viewfinder")
                .font(.system(size: 34))
                .foregroundStyle(Color.ink3)
                .accessibilityHidden(true)
            Text(camera == .denied
                ? "Camera access is off for Polished. Allow it in Settings, or type the digits below."
                : "This device can\u{2019}t scan barcodes. Type the digits, a P code, or a name below.")
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
                .multilineTextAlignment(.center)
                .accessibilityIdentifier("scan-unavailable")
            if camera == .denied {
                Button("Allow camera access in Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                }
                .buttonStyle(CompactButtonStyle())
            }
        }
        .padding(.horizontal, 28)
    }

    private var torchButton: some View {
        Button {
            torchIsOn.toggle()
        } label: {
            Image(systemName: torchIsOn ? "flashlight.on.fill" : "flashlight.off.fill")
                .font(.body.weight(.semibold))
                .frame(width: 44, height: 44)
        }
        .glassEffect(.regular.interactive(), in: .circle)
        .foregroundStyle(Color.ink)
        .accessibilityLabel(torchIsOn ? "Torch on" : "Torch off")
        .accessibilityIdentifier("scan-torch")
    }

    private var closeButton: some View {
        Button {
            dismiss()
        } label: {
            Text("Close")
                .font(.body.weight(.semibold))
                .padding(.horizontal, 16)
                .frame(minHeight: 44)
        }
        .glassEffect(.regular.interactive(), in: .capsule)
        .foregroundStyle(Color.ink)
        .accessibilityIdentifier("scan-close")
    }

    // MARK: Typed

    @ViewBuilder
    private func entry(_ scan: ScanModel) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            if camera == .ready {
                Text("Point at the barcode under the bottle")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                    .frame(maxWidth: .infinity)
                    .accessibilityIdentifier("scan-caption")
            }
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(Color.ink3)
                    .accessibilityHidden(true)
                TextField("Type the digits, a P code, or a name", text: $text)
                    .focused($fieldFocused)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .accessibilityIdentifier("scan-field")
                if !text.isEmpty {
                    Button {
                        text = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Color.ink3)
                            .frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .accessibilityLabel("Clear")
                }
            }
            .padding(.leading, 14)
            .padding(.trailing, text.isEmpty ? 14 : 0)
            .frame(minHeight: 48)
            .background(Color.fill, in: Capsule())
        }
    }

    // MARK: Result

    private func card(_ scan: ScanModel) -> some View {
        ScanResultView(scan: scan, purpose: purpose) {
            dismiss()
        }
        .id("scan-card")
    }

    private var learnedLink: some View {
        NavigationLink(value: ScanDestination.learnedCodes) {
            HStack {
                Text("Learned codes").foregroundStyle(Color.ink)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.ink3)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 50)
            .contentShape(Rectangle())
            .groupCard()
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("scan-learned-codes")
    }
}

enum ScanDestination: Hashable {
    case learnedCodes
}

private struct ScanCover: ViewModifier {
    @Binding var isPresented: Bool
    let purpose: ScanPurpose

    func body(content: Content) -> some View {
        content.fullScreenCover(isPresented: $isPresented) { ScanScreen(purpose: purpose) }
    }
}

extension View {
    /// The scan screen as a full-screen cover.
    func scanCover(isPresented: Binding<Bool>, purpose: ScanPurpose = .bottle) -> some View {
        modifier(ScanCover(isPresented: isPresented, purpose: purpose))
    }
}

/// The round scan button every entry point uses: Home's search row, the builder's picker.
struct ScanButton: View {
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: "barcode.viewfinder")
                .font(.title3)
                .foregroundStyle(Color.ink)
                .frame(width: 48, height: 48)
                .background(Color.fill, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .frame(minWidth: 48, minHeight: 48)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Scan a bottle")
        .accessibilityIdentifier("scan-button")
    }
}
