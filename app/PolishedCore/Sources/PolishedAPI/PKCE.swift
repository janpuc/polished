import CryptoKit
import Foundation

/// The app's half of the PKCE sign-in (RFC 7636, docs/NATIVE.md 2.4): a random verifier kept in
/// the app and its SHA-256 challenge sent to `/auth/app/start`.
public enum PKCE {
    /// 32 random bytes, base64url without padding.
    public static func makeVerifier() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        precondition(status == errSecSuccess, "no random bytes")
        return base64URL(Data(bytes))
    }

    /// `base64url(SHA256(verifier))`.
    public static func challenge(for verifier: String) -> String {
        base64URL(Data(SHA256.hash(data: Data(verifier.utf8))))
    }

    static func base64URL(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
