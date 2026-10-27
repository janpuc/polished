import Foundation
import PolishedModels

/// The server over HTTPS: one ephemeral `URLSession`, `Authorization: Bearer`, `User-Agent:
/// polished-ios/<version>`, and ETag revalidation through a `ResponseCache` (docs/NATIVE.md 2.3).
public final class LiveAPI: PolishedAPI {
    private let baseURL: URL
    private let userAgent: String
    private let token: @Sendable () -> String?
    private let onUnauthorized: @Sendable () -> Void
    private let cache: (any ResponseCache)?
    private let session: URLSession

    /// - Parameters:
    ///   - token: the bearer token, read on every call so a sign-in or sign-out takes effect at once.
    ///   - onUnauthorized: called on any 401, before the error is thrown (the session signs out).
    public init(
        baseURL: URL,
        appVersion: String,
        token: @escaping @Sendable () -> String?,
        cache: (any ResponseCache)? = nil,
        onUnauthorized: @escaping @Sendable () -> Void = {},
        session: URLSession = LiveAPI.makeSession()
    ) {
        self.baseURL = baseURL
        self.userAgent = "polished-ios/\(appVersion)"
        self.token = token
        self.cache = cache
        self.onUnauthorized = onUnauthorized
        self.session = session
    }

    /// One ephemeral session: no URL cache (the ETag store is ours), no waiting for connectivity
    /// (an offline call fails at once and the screen keeps its snapshot), 15 s timeout.
    public static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.waitsForConnectivity = false
        configuration.timeoutIntervalForRequest = 15
        return URLSession(configuration: configuration)
    }

    // MARK: GET

    public func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value {
        let key = endpoint.key
        let stored = await cache?.entry(for: key)
        var request = makeRequest("GET", endpoint.path, query: endpoint.query)
        if let etag = stored?.etag { request.setValue(etag, forHTTPHeaderField: "If-None-Match") }

        let (data, response) = try await perform(request)
        switch response.statusCode {
        case 304:
            guard let stored else { throw APIError.server(status: 304) }
            return try decode(Value.self, from: stored.body)
        case 200..<300:
            let value = try decode(Value.self, from: data)
            await cache?.save(
                CachedResponse(key: key, etag: response.value(forHTTPHeaderField: "ETag"), body: data, fetchedAt: Date()))
            return value
        default:
            throw failure(response.statusCode, data)
        }
    }

    public func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value? {
        guard let stored = await cache?.entry(for: endpoint.key) else { return nil }
        return try? decode(Value.self, from: stored.body)
    }

    // MARK: Writes

    public func send<Response: Decodable & Sendable>(_ request: Request<Response>) async throws -> Response {
        var http = makeRequest(request.method, request.path)
        if let body = request.body {
            http.httpBody = body
            http.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await perform(http)
        guard (200..<300).contains(response.statusCode) else { throw failure(response.statusCode, data) }
        if data.isEmpty, let none = NoContent() as? Response { return none }
        return try decode(Response.self, from: data)
    }

    // MARK: Auth

    public func exchange(_ exchange: ExchangeRequest) async throws -> ExchangeResponse {
        var request = makeRequest("POST", "/api/v1/auth/exchange", bearer: false)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try APICoding.makeEncoder().encode(exchange)
        let (data, response) = try await perform(request)
        guard (200..<300).contains(response.statusCode) else { throw failure(response.statusCode, data) }
        return try decode(ExchangeResponse.self, from: data)
    }

    public func revoke() async throws {
        let request = makeRequest("POST", "/api/v1/auth/revoke")
        let (data, response) = try await perform(request)
        guard (200..<300).contains(response.statusCode) else { throw failure(response.statusCode, data) }
    }

    // MARK: Plumbing

    private func makeRequest(
        _ method: String, _ path: String, query: [URLQueryItem] = [], bearer: Bool = true
    ) -> URLRequest {
        var components = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var request = URLRequest(url: components.url!)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(userAgent, forHTTPHeaderField: "User-Agent")
        if bearer, let token = token() { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return request
    }

    private func perform(_ request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw APIError.malformed("not an HTTP response") }
            return (data, http)
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
        } catch let error as URLError where error.code == .timedOut {
            throw APIError.timeout
        } catch is URLError {
            throw APIError.offline
        }
    }

    private func decode<Value: Decodable>(_ type: Value.Type, from data: Data) throws -> Value {
        do {
            return try APICoding.makeDecoder().decode(type, from: data)
        } catch {
            throw APIError.malformed(String(describing: error))
        }
    }

    private func failure(_ status: Int, _ data: Data) -> APIError {
        let error = APIError.from(status: status, body: data)
        if error == .unauthorized { onUnauthorized() }
        return error
    }
}
