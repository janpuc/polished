import Foundation
import PolishedModels

/// Answers from recorded responses (`spec/api/fixtures/*.json`, each `{request, status, body}`):
/// for SwiftUI previews and tests. A GET is matched by its path and query; a fixture recorded
/// without a query also answers the same path with one (`/shades?q=…` falls back to `/shades`).
public final class FixtureAPI: PolishedAPI {
    private struct Recording: Decodable {
        struct Request: Decodable {
            var method: String
            var path: String
        }

        var request: Request
        var status: Int
        var body: JSONValue
    }

    private let bodies: [String: Data]

    public init(directory: URL) throws {
        var bodies: [String: Data] = [:]
        let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
        for file in files where file.pathExtension == "json" {
            let recording = try JSONDecoder().decode(Recording.self, from: Data(contentsOf: file))
            guard recording.request.method == "GET", recording.status == 200 else { continue }
            bodies[recording.request.path] = try JSONEncoder().encode(recording.body)
        }
        self.bodies = bodies
    }

    public func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value {
        guard let body = bodies[endpoint.key] ?? bodies[endpoint.path] else { throw APIError.notFound }
        do {
            return try APICoding.makeDecoder().decode(Value.self, from: body)
        } catch {
            throw APIError.malformed(String(describing: error))
        }
    }

    public func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value? {
        try? await get(endpoint)
    }

    public func exchange(_ request: ExchangeRequest) async throws -> ExchangeResponse {
        throw APIError.badRequest(code: "bad_code", message: "Fixtures don't sign in.")
    }

    public func revoke() async throws {}
}

/// Any JSON, to carry a recording's body through untouched.
enum JSONValue: Codable, Sendable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Int.self) {
            self = .number(Double(value))
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case .bool(let value): try container.encode(value)
        case .number(let value):
            if value == value.rounded(), abs(value) < 1e15 { try container.encode(Int(value)) } else { try container.encode(value) }
        case .string(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        }
    }
}
