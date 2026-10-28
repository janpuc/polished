import Foundation
import PolishedAPI
import PolishedModels
import PolishedStore
import Synchronization
import Testing

/// Answers the builder's writes: every edit answers `answer(request)`, and the requests are kept.
final class StackAPI: PolishedAPI {
    let sent = Mutex<[String]>([])
    let answer: @Sendable (String) async throws -> StackSheet
    /// What `GET /stacks/{id}` (the reload after a refused edit) and `GET /stacks/pick` answer.
    let reload: StackSheet?
    let pick: Pick?

    init(reload: StackSheet? = nil, pick: Pick? = nil, answer: @escaping @Sendable (String) async throws -> StackSheet) {
        self.reload = reload
        self.pick = pick
        self.answer = answer
    }

    func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value {
        if let reload = reload as? Value { return reload }
        if let pick = pick as? Value { return pick }
        throw APIError.notFound
    }
    func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value? { nil }
    func exchange(_ request: ExchangeRequest) async throws -> ExchangeResponse { throw APIError.notFound }
    func revoke() async throws {}

    func send<Response: Decodable & Sendable>(_ request: Request<Response>) async throws -> Response {
        let line = "\(request.method) \(request.path)" + (request.body.flatMap { String(data: $0, encoding: .utf8) }.map { " \($0)" } ?? "")
        sent.withLock { $0.append(line) }
        let sheet = try await answer(line)
        guard let response = sheet as? Response else { throw APIError.malformed("the double answers sheets only") }
        return response
    }
}

private func fixtureSheet(_ file: String = "layer_add_second.json") throws -> StackSheet {
    try APICoding.makeDecoder().decode(StackSheet.self, from: recording(file).bodyData)
}

@MainActor
@Suite("BuilderModel")
struct BuilderModelTests {
    private func opened(_ api: StackAPI) async throws -> BuilderModel {
        let writes = WriteCoordinator(api: api)
        let model = BuilderModel(wheelID: 3, position: 3, api: api, writes: writes)
        await model.open()
        return model
    }

    @Test func labelsAndSummaryAsTheServerWritesThem() throws {
        #expect(BuilderModel.labels(count: 0) == [])
        #expect(BuilderModel.labels(count: 1) == [""])
        #expect(BuilderModel.labels(count: 2) == ["Base", "Top"])
        #expect(BuilderModel.labels(count: 5) == ["Base", "2nd", "3rd", "4th", "Top"])
        let sheet = try fixtureSheet()
        #expect(BuilderModel.summary(of: sheet.layers) == sheet.summary)
    }

    @Test func openingTheDraftShowsTheLayersAndWhetherItWasResumed() async throws {
        let sheet = try fixtureSheet("slot_draft_resumed.json")
        let model = try await opened(StackAPI { _ in sheet })
        #expect(model.resumed)
        #expect(model.sheet?.stackId == sheet.stackId)
    }

    @Test func coatsAndMovesShowAtOnceAndTheLastAnswerWins() async throws {
        let start = try fixtureSheet()
        var settled = start
        settled.layers[0].coats = start.layers[0].coats + 2
        settled.layers[0].tip.coats = start.layers[0].coats + 2
        let final = settled
        let api = StackAPI { line in line.contains("PATCH") ? final : start }
        let model = try await opened(api)
        let base = try #require(model.layers.first)
        for _ in 0..<2 { model.changeCoats(of: base, by: 1) }
        #expect(model.layers[0].coats == start.layers[0].coats + 2)
        #expect(model.sheet?.summary.contains("×\(start.layers[0].coats + 2)") == true)
        model.move(base, up: false)
        #expect(model.layers.map(\.title) == [start.layers[1].title, base.title])
        #expect(model.layers.map(\.label) == ["Base", "Top"])
        // The queue drains: three edits, in the order they were made.
        _ = try? await model.save(name: "", note: "", paintedOn: nil)
        let sent = api.sent.withLock { $0 }
        #expect(sent.filter { $0.hasPrefix("PATCH") }.count == 3)
        #expect(sent[1].contains("\"coats_delta\":1") && sent[3].contains("\"move\":\"down\""))
    }

    @Test func aCoatPastTheLimitsSendsNothing() async throws {
        let start = try fixtureSheet()
        let api = StackAPI { _ in start }
        let model = try await opened(api)
        let top = try #require(model.layers.last)
        model.changeCoats(of: top, by: -1)
        model.move(try #require(model.layers.first), up: true)
        #expect(api.sent.withLock { $0.count } == 1)
    }

    @Test func aFullStackRefusesAnotherLayer() async throws {
        var start = try fixtureSheet()
        let layer = start.layers[0]
        start.layers = (1...8).map { number in
            var copy = layer
            copy.id = number
            return copy
        }
        let final = start
        let api = StackAPI { _ in final }
        let model = try await opened(api)
        #expect(model.isFull)
        let shade = try APICoding.makeDecoder().decode(
            Pick.self, from: recording("stack_pick_barcode.json").bodyData
        ).items.first
        model.add(try #require(shade))
        #expect(model.notice == "A swatch holds up to 8 layers.")
        #expect(model.failures == 1)
        #expect(api.sent.withLock { $0.count } == 1)
    }

    @Test func aRefusedEditSaysWhy() async throws {
        let start = try fixtureSheet()
        let api = StackAPI { line in
            if line.hasPrefix("DELETE") { throw APIError.rule(code: "stack_full", message: "A swatch holds up to 8 layers.") }
            return start
        }
        let model = try await opened(api)
        model.remove(try #require(model.layers.first))
        #expect(model.layers.count == 1)
        _ = try? await model.cancel()
        #expect(model.notice == "A swatch holds up to 8 layers.")
        #expect(model.failures == 1)
    }

    // MARK: Local first

    /// The wheel page's tile for the slot: the saved layers, as the draft will copy them.
    private func preview(saved: StackSheet) -> BuilderPreview {
        let tile = Tile(
            position: 3, filled: true, stackId: 90, summary: saved.summary, layers: saved.layers)
        return BuilderPreview(wheel: StackWheel(id: 3, slug: "k3m9xq", name: "Holos"), tile: tile)
    }

    /// The saved swatch (one layer, ids 7) and the draft the server opens from it (ids 70).
    private func savedAndDraft() throws -> (saved: StackSheet, draft: StackSheet, added: StackSheet) {
        let added = try fixtureSheet()
        var saved = added
        saved.layers = [added.layers[0]]
        saved.layers[0].id = 7
        saved.summary = BuilderModel.summary(of: saved.layers)
        var draft = saved
        draft.layers[0].id = 70
        draft.stackId = 4
        var done = added
        done.layers[0].id = 70
        return (saved, draft, done)
    }

    /// Waits until the double has seen `count` requests.
    private func waitForRequests(_ api: StackAPI, count: Int) async {
        while api.sent.withLock({ $0.count }) < count { await Task.yield() }
    }

    private func pickedShade() throws -> ShadeRow {
        try #require(
            try APICoding.makeDecoder().decode(Pick.self, from: recording("stack_pick_barcode.json").bodyData).items.first)
    }

    @Test func openingShowsTheSavedLayersBeforeTheDraftAnswers() async throws {
        let (saved, draft, _) = try savedAndDraft()
        let (gate, release) = AsyncStream<Void>.makeStream()
        let api = StackAPI { _ in
            for await _ in gate { break }
            return draft
        }
        let model = BuilderModel(
            wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), preview: preview(saved: saved))
        let opening = Task { await model.open() }
        await waitForRequests(api, count: 1)
        #expect(model.draftID == nil)
        #expect(model.layers == saved.layers)
        #expect(model.sheet?.summary == saved.summary)
        #expect(model.sheet?.tip == saved.layers.map(\.tip))
        release.yield()
        await opening.value
        #expect(model.draftID == draft.stackId)
        #expect(model.layers == draft.layers)
        #expect(!model.resumed)
    }

    @Test func aSlotWithADraftShowsNoLayersUntilTheServerAnswers() async throws {
        let (saved, draft, _) = try savedAndDraft()
        var tile = preview(saved: saved)
        tile.tile.hasDraft = true
        let (gate, release) = AsyncStream<Void>.makeStream()
        let api = StackAPI { _ in
            for await _ in gate { break }
            return draft
        }
        let model = BuilderModel(wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), preview: tile)
        let opening = Task { await model.open() }
        await waitForRequests(api, count: 1)
        #expect(model.sheet == nil)
        model.add(try pickedShade())
        #expect(api.sent.withLock { $0.count } == 1)
        release.yield()
        await opening.value
        #expect(model.layers == draft.layers)
    }

    @Test func editsBeforeTheDraftAnswersAreSentAfterItWithTheDraftsIDs() async throws {
        let (saved, draft, added) = try savedAndDraft()
        let (gate, release) = AsyncStream<Void>.makeStream()
        let api = StackAPI { line in
            if line.contains("/draft") {
                for await _ in gate { break }
                return draft
            }
            return added
        }
        let model = BuilderModel(
            wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), preview: preview(saved: saved))
        let opening = Task { await model.open() }
        await waitForRequests(api, count: 1)
        model.add(try pickedShade())
        model.changeCoats(of: try #require(model.layers.first), by: 1)
        // At once on the screen, nothing sent yet.
        #expect(model.layers.count == 2)
        #expect(model.layers[0].coats == saved.layers[0].coats + 1)
        #expect(model.sheet?.summary.contains("\(try pickedShade().title)") == true)
        #expect(api.sent.withLock { $0.count } == 1)
        release.yield()
        await opening.value
        _ = try? await model.save(name: "", note: "", paintedOn: nil)
        let sent = api.sent.withLock { $0 }
        #expect(sent.count == 4)
        #expect(sent[0].hasPrefix("POST") && sent[0].contains("/draft"))
        #expect(sent[1].hasPrefix("POST") && sent[1].contains("/stacks/4/layers"))
        #expect(sent[2].hasPrefix("PATCH") && sent[2].contains("/stacks/4/layers/70"))
        #expect(sent[3].contains("/save"))
    }

    @Test func anAddThatFailsIsTakenBackAndTheSheetIsReloaded() async throws {
        let (saved, draft, _) = try savedAndDraft()
        let api = StackAPI(reload: draft) { line in
            if line.contains("/layers") { throw APIError.rule(code: "stack_full", message: "A swatch holds up to 8 layers.") }
            return draft
        }
        let model = BuilderModel(
            wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), preview: preview(saved: saved))
        await model.open()
        model.add(try pickedShade())
        #expect(model.layers.count == 2)
        #expect(model.layers.last?.shadeId == (try pickedShade()).id)
        _ = try? await model.save(name: "", note: "", paintedOn: nil)
        #expect(model.layers == draft.layers)
        #expect(model.notice == "A swatch holds up to 8 layers.")
        #expect(model.failures == 1)
    }

    @Test func aDraftThatWasThereAlreadyDropsTheEditsMadeOnTheSavedLayers() async throws {
        let (saved, draft, _) = try savedAndDraft()
        var other = draft
        other.resumed = true
        other.layers.append(draft.layers[0])
        other.layers[1].id = 71
        let resumed = other
        let (gate, release) = AsyncStream<Void>.makeStream()
        let api = StackAPI { line in
            if line.contains("/draft") {
                for await _ in gate { break }
                return resumed
            }
            return draft
        }
        let model = BuilderModel(
            wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), preview: preview(saved: saved))
        let opening = Task { await model.open() }
        await waitForRequests(api, count: 1)
        model.remove(try #require(model.layers.first))
        release.yield()
        await opening.value
        _ = try? await model.save(name: "", note: "", paintedOn: nil)
        #expect(model.resumed)
        #expect(model.layers == resumed.layers)
        #expect(api.sent.withLock { $0.filter { $0.hasPrefix("DELETE") }.count } == 0)
    }

    @Test func thePickersLastAnswerShowsAtOnceInTheNextBuilder() async throws {
        let list = try APICoding.makeDecoder().decode(Pick.self, from: recording("stack_pick_barcode.json").bodyData)
        let api = StackAPI(pick: list) { _ in try fixtureSheet() }
        let memory = PickMemory()
        let first = BuilderModel(wheelID: 3, position: 3, api: api, writes: WriteCoordinator(api: api), pickMemory: memory)
        #expect(first.pick == nil)
        await first.refreshPicker()
        #expect(first.pick == list)
        let second = BuilderModel(wheelID: 3, position: 4, api: api, writes: WriteCoordinator(api: api), pickMemory: memory)
        #expect(second.pick == list)
    }
}
