import SafariServices
import SwiftUI

/// SFSafariViewController for the shop's pages: the checkout and a shade's product page open in
/// the app's own sheet and come back with Done.
struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let controller = SFSafariViewController(url: url)
        controller.preferredControlTintColor = UIColor(Color.ink)
        return controller
    }

    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
}

extension URL: @retroactive Identifiable {
    public var id: String { absoluteString }
}

extension View {
    /// Presents `url` in Safari's sheet when it is set.
    func safariSheet(_ url: Binding<URL?>) -> some View {
        fullScreenCover(item: url) { SafariView(url: $0).ignoresSafeArea() }
    }
}
