import Foundation
import PolishedAPI
import PolishedModels
import PolishedStore
import Synchronization
import Testing

/// An API double: a closure answers every write, the order of the requests is kept.
final class ScriptedAPI: PolishedAPI {
    let sent = Mutex<[String]>([])
    /// What an update of a bottle answers.
    let bottle = Bottle(id: 3, shadeId: 1, state: .low)
    let answer: @Sendable (Int, String) async throws -> Void

    /// `answer(attempt, "METHOD path")` throws what the call should fail with; attempts count from 1.
    init(answer: @escaping @Sendable (Int, String) async throws -> Void = { _, _ in }) {
        self.answer = answer
    }

    func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value { throw APIError.notFound }
    func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value? { nil }
    func exchange(_ request: ExchangeRequest) async throws -> ExchangeResponse { throw APIError.notFound }
    func revoke() async throws {}

    func send<Response: Decodable & Sendable>(_ request: Request<Response>) async throws -> Response {
        let line = "\(request.method) \(request.path)"
        let attempt = sent.withLock { sent -> Int in
            sent.append(line)
            return sent.filter { $0 == line }.count
        }
        try await answer(attempt, line)
        if let none = NoContent() as? Response { return none }
        if let updated = bottle as? Response { return updated }
        if let recorded = WearRecorded(wornOn: "2026-10-27") as? Response { return recorded }
        throw APIError.malformed("the double only answers deletes and wear")
    }
}

/// A mutable cell for what the optimistic closures change, readable from the main actor.
@MainActor
final class Cell {
    var level = BottleState.full
}

@Suite("WriteCoordinator")
@MainActor
struct WriteCoordinatorTests {
    private func coordinator(_ api: ScriptedAPI, cache: (any ResponseCache)? = nil) -> WriteCoordinator {
        WriteCoordinator(api: api, cache: cache, retryDelay: .milliseconds(20))
    }

    @Test func aToggleAppliesBeforeTheServerAnswers() async throws {
        let api = ScriptedAPI { _, _ in try await Task.sleep(for: .milliseconds(200)) }
        let writes = coordinator(api)
        let cell = Cell()
        let task = Task { @MainActor in
            await writes.toggle(
                lane: "bottle-1", .wear(shadeID: 1), affecting: .wear, failure: "no",
                apply: { cell.level = .low }, revert: { cell.level = .full })
        }
        try await Task.sleep(for: .milliseconds(50))
        #expect(cell.level == .low, "applied while the request is still out")
        #expect(writes.revision == 0)
        let response = await task.value
        #expect(response?.wornOn == "2026-10-27")
        #expect(cell.level == .low)
        #expect(writes.status == nil)
        #expect(writes.revision == 1)
    }

    @Test func aFailedToggleIsUndoneWithAStatusLine() async {
        let api = ScriptedAPI { _, _ in throw APIError.server(status: 500) }
        let writes = coordinator(api)
        let cell = Cell()
        let response = await writes.toggle(
            lane: "bottle-1", .wear(shadeID: 1), affecting: .wear, failure: "Couldn't save. Still full.",
            apply: { cell.level = .half }, revert: { cell.level = .full })
        #expect(response == nil)
        #expect(cell.level == .full)
        #expect(writes.status?.message == "Couldn't save. Still full.")
        #expect(writes.status?.isFailure == true)
        #expect(writes.failures == 1)
        #expect(api.sent.withLock { $0.count } == 1, "a server error is not retried")
    }

    @Test func aTimeoutIsRetriedOnce() async {
        let api = ScriptedAPI { attempt, _ in if attempt == 1 { throw APIError.timeout } }
        let writes = coordinator(api)
        let response = await writes.toggle(
            lane: "x", .wear(shadeID: 1), affecting: .wear, failure: "no", apply: {}, revert: {})
        #expect(response != nil)
        #expect(api.sent.withLock { $0.count } == 2)
        #expect(writes.failures == 0)
    }

    @Test func aSecondTimeoutGivesUp() async {
        let api = ScriptedAPI { _, _ in throw APIError.timeout }
        let writes = coordinator(api)
        let cell = Cell()
        let response = await writes.toggle(
            lane: "x", .wear(shadeID: 1), affecting: .wear, failure: "Couldn't save.",
            apply: { cell.level = .empty }, revert: { cell.level = .full })
        #expect(response == nil)
        #expect(api.sent.withLock { $0.count } == 2)
        #expect(cell.level == .full)
    }

    @Test func togglesOfOneLaneAreSentInOrder() async {
        let api = ScriptedAPI { _, line in
            // The first request is the slow one; the second must still wait for it.
            if line.hasSuffix("/1") { try await Task.sleep(for: .milliseconds(60)) }
        }
        let writes = coordinator(api)
        async let first = writes.toggle(lane: "bottle-1", .wear(shadeID: 1), affecting: .wear, failure: "", apply: {}, revert: {})
        async let second = writes.toggle(lane: "bottle-1", .wear(shadeID: 2), affecting: .wear, failure: "", apply: {}, revert: {})
        _ = await (first, second)
        #expect(api.sent.withLock { $0 } == ["POST /api/v1/wear/1", "POST /api/v1/wear/2"])
    }

    @Test func aWriteForgetsTheSnapshotsItMadeStale() async throws {
        let cache = try SnapshotStore.make(inMemory: true)
        let stamp = Date()
        for key in ["/api/v1/home", "/api/v1/shades?q=x", "/api/v1/shades/13", "/api/v1/bottles", "/api/v1/wishlist", "/api/v1/wheels", "/api/v1/me"] {
            await cache.save(CachedResponse(key: key, etag: nil, body: Data(), fetchedAt: stamp))
        }
        let writes = coordinator(ScriptedAPI(), cache: cache)
        _ = try await writes.perform(.deleteBottle(id: 3), affecting: .bottleChange)
        #expect(await cache.entry(for: "/api/v1/home") == nil)
        #expect(await cache.entry(for: "/api/v1/shades?q=x") == nil)
        #expect(await cache.entry(for: "/api/v1/shades/13") == nil)
        #expect(await cache.entry(for: "/api/v1/bottles") == nil)
        #expect(await cache.entry(for: "/api/v1/wishlist") == nil)
        #expect(await cache.entry(for: "/api/v1/wheels") != nil, "a bottle does not touch the wheels")
        #expect(await cache.entry(for: "/api/v1/me") != nil)
        #expect(writes.revision == 1)
    }

    @Test func aRefusedWriteChangesNothing() async throws {
        let cache = try SnapshotStore.make(inMemory: true)
        await cache.save(CachedResponse(key: "/api/v1/bottles", etag: nil, body: Data(), fetchedAt: Date()))
        let fields = ["state": "Pick full, half, low or empty."]
        let api = ScriptedAPI { _, _ in throw APIError.validation(field: "state", message: fields["state"]!, fields: fields) }
        let writes = coordinator(api, cache: cache)
        await #expect(throws: APIError.self) { try await writes.perform(.deleteBottle(id: 3), affecting: .bottleChange) }
        #expect(await cache.entry(for: "/api/v1/bottles") != nil)
        #expect(writes.revision == 0)
    }

    @Test func theStatusLineGoesAway() async throws {
        let writes = coordinator(ScriptedAPI())
        writes.show("Learned P321")
        #expect(writes.status?.message == "Learned P321")
        writes.dismissStatus()
        #expect(writes.status == nil)
    }
}

@Suite("Level change")
@MainActor
struct LevelChangeTests {
    /// One bottle's state, as a screen's resource would hold it.
    final class Shelf {
        var bottles = [Bottle(id: 3, shadeId: 1, state: .full)]
        func edit(_ id: Int, _ change: (inout Bottle) -> Void) {
            if let index = bottles.firstIndex(where: { $0.id == id }) { change(&bottles[index]) }
        }
    }

    @Test func theLevelChangesAtOnceAndTakesTheServersBottle() async {
        let api = ScriptedAPI()
        let writes = WriteCoordinator(api: api, retryDelay: .milliseconds(10))
        let shelf = Shelf()
        await writes.changeLevel(shelf.bottles[0], to: .half) { id, change in shelf.edit(id, change) }
        #expect(api.sent.withLock { $0 } == ["PATCH /api/v1/bottles/3"])
        #expect(shelf.bottles[0].state == .low, "the server's answer replaced the guess")
    }

    @Test func aRefusedLevelGoesBackAndSaysWhich() async {
        let api = ScriptedAPI { _, _ in throw APIError.server(status: 503) }
        let writes = WriteCoordinator(api: api, retryDelay: .milliseconds(10))
        let shelf = Shelf()
        await writes.changeLevel(shelf.bottles[0], to: .empty) { id, change in shelf.edit(id, change) }
        #expect(shelf.bottles[0].state == .full)
        #expect(writes.status?.message == "Couldn\u{2019}t save. Still full.")
    }

    @Test func theSameLevelSendsNothing() async {
        let api = ScriptedAPI()
        let writes = WriteCoordinator(api: api)
        let shelf = Shelf()
        await writes.changeLevel(shelf.bottles[0], to: .full) { id, change in shelf.edit(id, change) }
        #expect(api.sent.withLock { $0.isEmpty })
    }
}

@Suite("SaveAction")
@MainActor
struct SaveActionTests {
    @Test func theSpinnerWaitsForTheDelay() async throws {
        let save = SaveAction(progressDelay: .milliseconds(80))
        let task = Task { @MainActor in
            await save.run { try await Task.sleep(for: .milliseconds(250)) }
        }
        try await Task.sleep(for: .milliseconds(30))
        #expect(save.isRunning)
        #expect(!save.showsProgress, "a quick wait shows nothing")
        try await Task.sleep(for: .milliseconds(120))
        #expect(save.showsProgress)
        _ = await task.value
        #expect(!save.isRunning && !save.showsProgress)
    }

    @Test func aFastAnswerNeverShowsTheSpinner() async {
        let save = SaveAction(progressDelay: .milliseconds(200))
        let value = await save.run { 42 }
        #expect(value == 42)
        #expect(!save.showsProgress)
    }

    @Test func aValidationErrorSplitsIntoFields() async {
        let save = SaveAction()
        let result: Int? = await save.run {
            throw APIError.validation(
                field: "bought_on", message: "That date is in the future.",
                fields: ["bought_on": "That date is in the future.", "price_paid_cents": "Use an amount like 15.50."])
        }
        #expect(result == nil)
        #expect(save.fieldErrors["price_paid_cents"] == "Use an amount like 15.50.")
        #expect(save.generalError == nil, "every message belongs to a field")
        save.clearError()
        #expect(save.error == nil)
    }

    @Test func anOfflineErrorIsGeneral() async {
        let save = SaveAction()
        let _: Int? = await save.run { throw APIError.offline }
        #expect(save.generalError == "You're offline.")
        #expect(save.fieldErrors.isEmpty)
    }
}
