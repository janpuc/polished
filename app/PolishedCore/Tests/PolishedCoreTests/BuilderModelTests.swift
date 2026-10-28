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

    init(answer: @escaping @Sendable (String) async throws -> StackSheet) {
        self.answer = answer
    }

    func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value { throw APIError.notFound }
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
}
