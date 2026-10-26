import Foundation
import PolishedModels

/// What a call to the server can fail with (docs/NATIVE.md 2.3).
public enum APIError: Error, Sendable, Equatable {
    case unauthorized
    case notFound
    case conflict(code: String)
    case validation(fields: [String: String])
    case offline
    case server(status: Int)
}

/// The signed-in person and the server's settings: `GET /api/v1/me`.
public struct Me: Codable, Sendable, Hashable {
    public struct User: Codable, Sendable, Hashable {
        public var sub: String
        public var name: String
        public var firstName: String

        private enum CodingKeys: String, CodingKey {
            case sub, name
            case firstName = "first_name"
        }
    }

    public var user: User
}

/// One async method per contract endpoint (`spec/api/openapi.yaml`). Run 2 fills it in.
public protocol PolishedAPI: Sendable {
    func me() async throws -> Me
}
