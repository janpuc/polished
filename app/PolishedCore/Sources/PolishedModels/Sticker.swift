import Foundation

/// What a sticker's first link opens, compared with the wheel being tagged (docs/NATIVE.md 5.3,
/// "Check the sticker").
public enum StickerVerdict: Hashable, Sendable {
    /// The sticker opens this wheel.
    case thisWheel
    /// It opens another wheel of ours, by name.
    case otherWheel(name: String)
    /// It opens a wheel address of ours that no wheel answers to any more.
    case goneWheel
    /// It opens a shade of ours.
    case shade
    /// It holds a link, but not one of ours: its host and path as the sticker has it.
    case notOurs(String)
    /// It holds nothing readable.
    case blank

    /// `url` is the sticker's first URI record (nil for a blank or text-only sticker). A link is
    /// ours when it is a wheel or shade link on the host of `tagURL` (the server's public address).
    public static func of(url: URL?, wheelSlug: String, tagURL: String, others: [WheelRef]) -> StickerVerdict {
        guard let url else { return .blank }
        let ours = URL(string: tagURL)?.host(percentEncoded: false)?.lowercased()
        guard let host = url.host(percentEncoded: false)?.lowercased(), host == ours, let link = DeepLink(url: url) else {
            return .notOurs(Self.describe(url))
        }
        switch link {
        case .wheel(let slug):
            if slug == wheelSlug { return .thisWheel }
            if let other = others.first(where: { $0.slug == slug }) { return .otherWheel(name: other.name) }
            return .goneWheel
        case .shade:
            return .shade
        }
    }

    /// "polished.janpuc.com/w/k3m9xq": the link without its scheme, short enough for a sentence.
    static func describe(_ url: URL) -> String {
        let host = url.host(percentEncoded: false) ?? ""
        let text = host + url.path(percentEncoded: false)
        return text.isEmpty ? url.absoluteString : String(text.prefix(60))
    }
}
