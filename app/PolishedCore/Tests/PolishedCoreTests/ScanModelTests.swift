import Foundation
import PolishedAPI
import PolishedModels
import PolishedStore
import Testing

@testable import PolishedStore

/// The recordings of typed lookups were made without `via`; this answers `via=typed` from them.
private struct TypedAsRecorded: PolishedAPI {
    let base: FixtureAPI

    func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value {
        let query = endpoint.query.filter { !($0.name == "via" && $0.value == "typed") }
        return try await base.get(Endpoint<Value>(endpoint.path, query: query))
    }

    func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value? { nil }

    func send<Response: Decodable & Sendable>(_ request: Request<Response>) async throws -> Response {
        try await base.send(request)
    }

    func exchange(_ request: ExchangeRequest) async throws -> ExchangeResponse { try await base.exchange(request) }
    func revoke() async throws {}
}

@Suite("Scan model")
@MainActor
struct ScanModelTests {
    private func model() throws -> ScanModel {
        let api = TypedAsRecorded(base: try FixtureAPI(directory: Fixtures.url("api/fixtures")))
        return ScanModel(api: api, writes: WriteCoordinator(api: api))
    }

    private func shade() throws -> ShadeRow {
        try APICoding.makeDecoder().decode(IdentifierSaved.self, from: recording("identifier_learn.json").bodyData).shade
    }

    @Test("typed digits that are not a barcode are a name search")
    func typedShortNumber() async throws {
        let scan = try model()
        await scan.lookup(typed: "259")
        guard case .results(let query, let found) = scan.phase else {
            Issue.record("phase is \(scan.phase)")
            return
        }
        #expect(query == "259")
        #expect(found.items.isEmpty)
    }

    @Test("typed nothing clears the card")
    func typedNothing() async throws {
        let scan = try model()
        await scan.lookup(typed: "259")
        await scan.lookup(typed: "   ")
        #expect(scan.phase == .idle)
    }

    @Test("a scanned barcode nobody taught is unknown, and learning it keeps the card on the shade")
    func unknownThenLearned() async throws {
        let scan = try model()
        let accepted = await scan.recognise(barcode: "5901234123457")
        #expect(accepted)
        #expect(scan.recognitions == 1)
        #expect(scan.phase == .unknownCode("5901234123457"))
        await scan.learn(try shade())
        guard case .match(let found) = scan.phase else {
            Issue.record("phase is \(scan.phase)")
            return
        }
        #expect(found.shade.title == "Thirst Trap")
        #expect(found.identifierID == 2)
        #expect(found.notice == "Saved. 5901234123457 is now Thirst Trap.")
        #expect(found.lead == "Barcode 5901234123457 is")
    }

    @Test("the camera reporting one bottle again and again asks once")
    func sameBarcodeIsIgnored() async throws {
        let scan = try model()
        #expect(await scan.recognise(barcode: "5901234123457"))
        #expect(await scan.recognise(barcode: "5901234123457") == false)
        #expect(await scan.recognise(barcode: "590123412345 7") == false)
        #expect(scan.recognitions == 1)
    }

    @Test("a misread barcode is invalid without a request")
    func misread() async throws {
        let scan = try model()
        #expect(await scan.recognise(barcode: "5901234123458") == false)
        #expect(scan.phase == .invalid(text: "5901234123458", scanned: true))
        #expect(scan.recognitions == 0)
    }

    @Test("a name is searched")
    func results() async throws {
        let scan = try model()
        await scan.lookup(typed: "flakie")
        guard case .results(let query, let found) = scan.phase else {
            Issue.record("phase is \(scan.phase)")
            return
        }
        #expect(query == "flakie")
        #expect(found.items.first?.title == "Flakie Holo Taco")
    }

    @Test("every outcome of the recordings maps to a phase")
    func outcomes() throws {
        let decoder = APICoding.makeDecoder()
        func phase(_ file: String, scanned: Bool = false) throws -> ScanPhase {
            let answer = try decoder.decode(Lookup.self, from: recording(file).bodyData)
            return ScanModel.phase(for: answer, asked: "asked", scanned: scanned)
        }
        #expect(try phase("lookup_unknown_code.json") == .unknownCode("5901234123457"))
        #expect(try phase("lookup_invalid_code.json", scanned: true) == .invalid(text: "asked", scanned: true))
        guard case .match(let found) = try phase("lookup_match.json") else {
            Issue.record("lookup_match is not a match")
            return
        }
        #expect(found.identifierID != nil)
    }
}

@Suite("Sticker verdict")
struct StickerVerdictTests {
    private let others = [
        try! JSONDecoder().decode(WheelRef.self, from: Data(#"{"id": 2, "name": "Toppers", "slug": "7b2vdc"}"#.utf8))
    ]
    private func verdict(_ text: String?) -> StickerVerdict {
        StickerVerdict.of(
            url: text.flatMap(URL.init(string:)), wheelSlug: "k3m9xq", tagURL: "https://polished.janpuc.com/w/k3m9xq",
            others: others)
    }

    @Test func thisWheel() { #expect(verdict("https://polished.janpuc.com/w/k3m9xq") == .thisWheel) }

    @Test func anotherWheelByName() {
        #expect(verdict("https://polished.janpuc.com/w/7b2vdc") == .otherWheel(name: "Toppers"))
    }

    @Test func aWheelNoWheelAnswersTo() { #expect(verdict("https://polished.janpuc.com/w/zzzzzz") == .goneWheel) }

    @Test func aShade() { #expect(verdict("https://polished.janpuc.com/shades/13") == .shade) }

    @Test func notOurs() {
        #expect(verdict("https://example.com/w/k3m9xq") == .notOurs("example.com/w/k3m9xq"))
        #expect(verdict("https://polished.janpuc.com/wishlist") == .notOurs("polished.janpuc.com/wishlist"))
    }

    @Test func blank() { #expect(verdict(nil) == .blank) }
}
