import Foundation

/// What a call to the server can fail with (docs/NATIVE.md 2.3, 3 "Errors").
public enum APIError: Error, Sendable, Equatable {
    /// 401: the token is missing, unknown or revoked. The session signs out.
    case unauthorized
    case forbidden
    case notFound
    /// 409 `not_a_draft`, `sync_running`.
    case conflict(code: String, message: String)
    /// 422 `validation`: `field` and `message` are the first wrong input, `fields` lists every one.
    case validation(field: String?, message: String, fields: [String: String])
    /// 422 with a rule's own code: `stack_full`, `empty_stack`, `same_wheel`.
    case rule(code: String, message: String)
    /// 429 `cooldown`.
    case cooldown(retryAfterSeconds: Int, message: String)
    /// 400 `bad_request`, `bad_code`.
    case badRequest(code: String, message: String)
    /// No connection, or the server unreachable.
    case offline
    /// The server did not answer in time; the one error a toggle retries.
    case timeout
    case server(status: Int)
    /// The body did not match the contract.
    case malformed(String)

    /// Her words where the server sent them, else ours.
    public var message: String {
        switch self {
        case .unauthorized: "Sign in again."
        case .forbidden: "This account can't do that."
        case .notFound: "That isn't here any more."
        case .conflict(_, let message), .rule(_, let message), .badRequest(_, let message): message
        case .validation(_, let message, _): message
        case .cooldown(_, let message): message
        case .offline: "You're offline."
        case .timeout: "The server took too long to answer."
        case .server: "The server had a problem. Try again in a moment."
        case .malformed: "The server sent something the app doesn't understand."
        }
    }
}

extension APIError {
    private struct Envelope: Decodable {
        struct Body: Decodable {
            var code: String
            var message: String
            var field: String?
            var fields: [String: String]?
            var retryAfterS: Int?
        }

        var error: Body
    }

    /// The error for a response that was not a success: `{"error": {"code", "message", ...}}`.
    public static func from(status: Int, body: Data) -> APIError {
        let envelope = try? JSONDecoder.snake.decode(Envelope.self, from: body).error
        let message = envelope?.message ?? ""
        let code = envelope?.code ?? ""
        switch status {
        case 401: return .unauthorized
        case 403: return .forbidden
        case 404: return .notFound
        case 409: return .conflict(code: code, message: message)
        case 400: return .badRequest(code: code, message: message)
        case 422:
            if code == "validation", let envelope {
                var fields = envelope.fields ?? [:]
                if let field = envelope.field, fields[field] == nil { fields[field] = envelope.message }
                return .validation(field: envelope.field, message: message, fields: fields)
            }
            return .rule(code: code, message: message)
        case 429: return .cooldown(retryAfterSeconds: envelope?.retryAfterS ?? 0, message: message)
        default: return .server(status: status)
        }
    }
}

extension JSONDecoder {
    fileprivate static var snake: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}
