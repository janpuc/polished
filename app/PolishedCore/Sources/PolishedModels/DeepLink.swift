import Foundation

/// Where a link into the app lands (docs/NATIVE.md 2.3): `/w/<slug>` is a wheel, `/shades/<id>` a
/// shade. Anything else is not ours and is ignored. The slug alphabet is the server's (six
/// characters of `0-9 a-z` without i, l, o, u) and an id is plain digits, so a crafted link
/// cannot carry a path or a query into a request.
public enum DeepLink: Hashable, Sendable {
    case wheel(slug: String)
    case shade(id: Int)

    private static let slugCharacters = Set("0123456789abcdefghjkmnpqrstvwxyz")

    public init?(url: URL) {
        guard let scheme = url.scheme?.lowercased(), scheme == "https" || scheme == "http" else { return nil }
        let parts = url.path.split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        // "/w/k3m9xq" splits into ["", "w", "k3m9xq"]; a trailing slash is one more empty part.
        guard parts.count == 3 || (parts.count == 4 && parts[3].isEmpty), parts[0].isEmpty else { return nil }
        switch parts[1] {
        case "w":
            guard Self.isSlug(parts[2]) else { return nil }
            self = .wheel(slug: parts[2])
        case "shades":
            guard parts[2].count <= 9, !parts[2].isEmpty, parts[2].allSatisfy({ $0.isASCII && $0.isNumber }),
                let id = Int(parts[2]), id > 0
            else { return nil }
            self = .shade(id: id)
        default:
            return nil
        }
    }

    public static func isSlug(_ text: String) -> Bool {
        text.count == 6 && text.allSatisfy { slugCharacters.contains($0) }
    }
}
