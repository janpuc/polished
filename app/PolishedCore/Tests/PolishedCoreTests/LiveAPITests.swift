import Foundation
import PolishedAPI
import PolishedModels
import PolishedStore
import Synchronization
import Testing

/// A `URLProtocol` that answers from a closure, for `LiveAPI` without a network.
final class StubProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var handler: (@Sendable (URLRequest) -> (Int, [String: String], Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.handler else { return }
        let (status, headers, body) = handler(request)
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers)!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

/// The stub's handler is global, so these suites run one after another.
@Suite("LiveAPI", .serialized)
struct LiveAPITests {
    private func makeAPI(
        token: String? = "dev", cache: (any ResponseCache)? = nil,
        onUnauthorized: @escaping @Sendable () -> Void = {}
    ) -> LiveAPI {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubProtocol.self]
        return LiveAPI(
            baseURL: URL(string: "http://127.0.0.1:8080")!, appVersion: "9.9", token: { token }, cache: cache,
            onUnauthorized: onUnauthorized, session: URLSession(configuration: configuration))
    }

    private func meBody() throws -> Data { try Fixtures.data("api/fixtures/me.json").extractingBody() }

    @Test func sendsBearerAndUserAgent() async throws {
        let seen = Mutex<URLRequest?>(nil)
        let body = try meBody()
        StubProtocol.handler = { request in
            seen.withLock { $0 = request }
            return (200, ["ETag": "\"abc\""], body)
        }
        let me = try await makeAPI().me()
        #expect(me.user.firstName == "Nikola")
        let request = try #require(seen.withLock { $0 })
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer dev")
        #expect(request.value(forHTTPHeaderField: "User-Agent") == "polished-ios/9.9")
        #expect(request.url?.path == "/api/v1/me")
    }

    @Test func revalidatesWithTheETagAndReadsTheCacheOn304() async throws {
        let store = try SnapshotStore.make(inMemory: true)
        let body = try meBody()
        let sentTags = Mutex<[String?]>([])
        StubProtocol.handler = { request in
            let tag = request.value(forHTTPHeaderField: "If-None-Match")
            sentTags.withLock { $0.append(tag) }
            return tag == nil ? (200, ["ETag": "\"v1\""], body) : (304, [:], Data())
        }
        let api = makeAPI(cache: store)
        #expect(await api.cached(Endpoint<Me>.me()) == nil)
        let first = try await api.me()
        let second = try await api.me()
        #expect(first == second)
        #expect(sentTags.withLock { $0 } == [nil, "\"v1\""])
        #expect(await api.cached(Endpoint<Me>.me())?.user.name == "Nikola Example")
    }

    @Test func a401SignsOut() async throws {
        let signedOut = Mutex(false)
        StubProtocol.handler = { _ in (401, [:], Data(#"{"error":{"code":"unauthorized","message":"Sign in again."}}"#.utf8)) }
        let api = makeAPI(onUnauthorized: { signedOut.withLock { $0 = true } })
        await #expect(throws: APIError.unauthorized) { try await api.home() }
        #expect(signedOut.withLock { $0 })
    }

    @Test func mapsStatuses() async throws {
        StubProtocol.handler = { _ in (404, [:], Data(#"{"error":{"code":"not_found","message":"x"}}"#.utf8)) }
        await #expect(throws: APIError.notFound) { try await makeAPI().shade(id: 999_999) }
        StubProtocol.handler = { _ in (503, [:], Data()) }
        await #expect(throws: APIError.server(status: 503)) { try await makeAPI().home() }
        StubProtocol.handler = { _ in (200, [:], Data(#"{"nope":1}"#.utf8)) }
        await #expect(throws: APIError.self) { try await makeAPI().home() }
    }

    @Test func exchangePostsJSONWithoutABearer() async throws {
        let seen = Mutex<URLRequest?>(nil)
        let sentBody = Mutex<Data?>(nil)
        let response = try Fixtures.data("api/fixtures/auth_exchange.json").extractingBody()
        StubProtocol.handler = { request in
            seen.withLock { $0 = request }
            sentBody.withLock { $0 = request.bodyStreamData() }
            return (200, [:], response)
        }
        let reply = try await makeAPI().exchange(
            ExchangeRequest(code: "c", verifier: "v", deviceName: "Nikola's iPhone", appVersion: "1.0.0"))
        #expect(reply.token.hasPrefix("example-token"))
        let request = try #require(seen.withLock { $0 })
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "Authorization") == nil)
        let posted = try #require(sentBody.withLock { $0 })
        let json = try #require(try JSONSerialization.jsonObject(with: posted) as? [String: String])
        #expect(json["device_name"] == "Nikola's iPhone")
        #expect(json["app_version"] == "1.0.0")
        #expect(json["platform"] == "ios")
    }

    @Test func sendsAWriteWithItsBodyAndDecodesTheAnswer() async throws {
        let seen = Mutex<URLRequest?>(nil)
        let body = Mutex<Data?>(nil)
        let answer = try Fixtures.data("api/fixtures/wishlist_add.json").extractingBody()
        StubProtocol.handler = { request in
            seen.withLock { $0 = request }
            body.withLock { $0 = request.bodyStreamData() }
            return (200, [:], answer)
        }
        let item = try await makeAPI().send(.wish(shadeID: 1, priority: 2))
        #expect(item.id == 4)
        let request = try #require(seen.withLock { $0 })
        #expect(request.httpMethod == "PUT")
        #expect(request.url?.path == "/api/v1/shades/1/wishlist")
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer dev")
        #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")
        #expect(body.withLock { $0 } == Data(#"{"priority":2}"#.utf8))
    }

    @Test func aNoContentAnswerIsNoContent() async throws {
        StubProtocol.handler = { _ in (204, [:], Data()) }
        let none = try await makeAPI().send(.deleteBottle(id: 7))
        #expect(none == NoContent())
    }

    @Test func aWriteRefusedWithFieldsThrowsThem() async throws {
        let answer = try Fixtures.data("api/fixtures/error_validation_bottle.json").extractingBody()
        StubProtocol.handler = { _ in (422, [:], answer) }
        do {
            _ = try await makeAPI().send(.addBottle(shadeID: 1, BottleRequest()))
            Issue.record("expected a validation error")
        } catch APIError.validation(let field, _, let fields) {
            #expect(field == "state")
            #expect(fields.count == 3)
        }
    }

    @Test func aCooldownCarriesItsWait() async throws {
        let answer = try Fixtures.data("api/fixtures/error_cooldown.json").extractingBody()
        StubProtocol.handler = { _ in (429, ["Retry-After": "3600"], answer) }
        do {
            _ = try await makeAPI().send(.runSync())
            Issue.record("expected a cooldown")
        } catch APIError.cooldown(let seconds, _) {
            #expect(seconds == 3600)
        }
    }

    @Test func aSyncAlreadyRunningIsAConflict() async throws {
        StubProtocol.handler = { _ in
            (409, [:], Data(#"{"error":{"code":"sync_running","message":"A sync is already running."}}"#.utf8))
        }
        do {
            _ = try await makeAPI().send(.runSync())
            Issue.record("expected a conflict")
        } catch APIError.conflict(let code, _) {
            #expect(code == "sync_running")
        }
    }

    @Test func aWriteWithoutATokenSignsOutOn401() async throws {
        let signedOut = Mutex(false)
        StubProtocol.handler = { _ in (401, [:], Data(#"{"error":{"code":"unauthorized","message":"x"}}"#.utf8)) }
        let api = makeAPI(token: nil, onUnauthorized: { signedOut.withLock { $0 = true } })
        await #expect(throws: APIError.unauthorized) { try await api.send(.wear(shadeID: 1)) }
        #expect(signedOut.withLock { $0 })
    }
}

@Suite("FixtureAPI")
struct FixtureAPITests {
    @Test func answersFromTheRecordings() async throws {
        let api = try FixtureAPI(directory: Fixtures.url("api/fixtures"))
        let home = try await api.home()
        #expect(home.counts.bottles == 5)
        let wheel = try await api.wheel(slug: "k3m9xq")
        #expect(wheel.tiles.count == 20)
        await #expect(throws: APIError.notFound) { try await api.shade(id: 999_999) }
    }
}

extension Data {
    /// The `body` of a recorded fixture.
    func extractingBody() throws -> Data {
        let root = try #require(try JSONSerialization.jsonObject(with: self) as? [String: Any])
        let body = try #require(root["body"])
        return try JSONSerialization.data(withJSONObject: body)
    }
}

extension URLRequest {
    /// URLProtocol sees a request's body as a stream.
    func bodyStreamData() -> Data? {
        if let httpBody { return httpBody }
        guard let stream = httpBodyStream else { return nil }
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count <= 0 { break }
            data.append(buffer, count: count)
        }
        return data
    }
}
