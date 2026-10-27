import Foundation
import PolishedModels

/// Answers from recorded responses (`spec/api/fixtures/*.json`, each `{request, status, body}`):
/// for SwiftUI previews and tests. A GET is matched by its path and query; a fixture recorded
/// without a query also answers the same path with one (`/shades?q=…` falls back to `/shades`).
/// A write is answered by the first success recorded for its method and path (by file name); the
/// error recordings are for the tests of `APIError`.
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
    /// Every write by `"METHOD path"`, with the status it was recorded with.
    private let writes: [String: (status: Int, body: Data)]

    public init(directory: URL) throws {
        var bodies: [String: Data] = [:]
        var writes: [String: (status: Int, body: Data)] = [:]
        let files = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
        for file in files.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) where file.pathExtension == "json" {
            let recording = try JSONDecoder().decode(Recording.self, from: Data(contentsOf: file))
            let body = try JSONEncoder().encode(recording.body)
            if recording.request.method != "GET" {
                let key = "\(recording.request.method) \(recording.request.path)"
                // The first success wins; a failure only fills a gap.
                let isSuccess = (200..<300).contains(recording.status)
                let keepsEarlier = writes[key].map { (200..<300).contains($0.status) || !isSuccess } ?? false
                if !keepsEarlier { writes[key] = (recording.status, body) }
            } else if recording.status == 200 {
                bodies[recording.request.path] = body
            }
        }
        self.bodies = bodies
        self.writes = writes
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

    /// A write is answered by the recording of the same method and path, whatever its body.
    public func send<Response: Decodable & Sendable>(_ request: Request<Response>) async throws -> Response {
        guard let recorded = writes["\(request.method) \(request.path)"] else { throw APIError.notFound }
        guard (200..<300).contains(recorded.status) else { throw APIError.from(status: recorded.status, body: recorded.body) }
        if recorded.status == 204, let none = NoContent() as? Response { return none }
        do {
            return try APICoding.makeDecoder().decode(Response.self, from: recorded.body)
        } catch {
            throw APIError.malformed(String(describing: error))
        }
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
