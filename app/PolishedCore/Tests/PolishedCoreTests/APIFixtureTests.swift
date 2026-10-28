import Foundation
import PolishedAPI
import PolishedModels
import Testing

/// A recorded response of `spec/api/fixtures/`: `{request, status, body}`.
struct Recording {
    var method: String
    var path: String
    var requestBody: Any?
    var status: Int
    var body: Any
    var bodyData: Data
}

func recording(_ file: String) throws -> Recording {
    let root = try #require(try Fixtures.json("api/fixtures/\(file)") as? [String: Any])
    let request = try #require(root["request"] as? [String: Any])
    let body = try #require(root["body"])
    let data = try JSONSerialization.data(withJSONObject: body, options: [.fragmentsAllowed])
    return Recording(
        method: request["method"] as? String ?? "", path: request["path"] as? String ?? "",
        requestBody: request["body"],
        status: root["status"] as? Int ?? 0, body: body, bodyData: data)
}

/// The keys of `original` (non-null values) that `reencoded` lacks: what the DTO silently dropped.
func droppedKeys(_ original: Any, _ reencoded: Any, path: String = "") -> [String] {
    switch (original, reencoded) {
    case (let original as [String: Any], let reencoded as [String: Any]):
        return original.flatMap { key, value -> [String] in
            if value is NSNull { return [] }
            guard let other = reencoded[key] else { return ["\(path)/\(key)"] }
            return droppedKeys(value, other, path: "\(path)/\(key)")
        }
    case (let original as [Any], let reencoded as [Any]):
        return zip(original, reencoded).enumerated().flatMap { index, pair in
            droppedKeys(pair.0, pair.1, path: "\(path)[\(index)]")
        }
    default:
        return []
    }
}

/// One GET fixture and the DTO it must decode into.
private struct GetFixture: Sendable, CustomTestStringConvertible {
    var file: String
    var check: @Sendable (String) throws -> Void
    var testDescription: String { file }

    init<T: Codable & Sendable>(_ file: String, _ type: T.Type) {
        self.file = file
        check = { file in
            let recorded = try recording(file)
            let value = try APICoding.makeDecoder().decode(T.self, from: recorded.bodyData)
            let encoded = try JSONSerialization.jsonObject(with: APICoding.makeEncoder().encode(value))
            let dropped = droppedKeys(recorded.body, encoded)
            #expect(dropped.isEmpty, "\(file): the DTO does not carry \(dropped.sorted())")
        }
    }
}

private let getFixtures: [GetFixture] = [
    .init("me.json", Me.self),
    .init("auth_devices.json", Devices.self),
    .init("home.json", Home.self),
    .init("home_another.json", Home.self),
    .init("shades_page.json", ShadePage.self),
    .init("shades_search.json", ShadePage.self),
    .init("shades_filtered.json", ShadePage.self),
    .init("shades_facets.json", Facets.self),
    .init("shade_detail.json", ShadeDetail.self),
    .init("shade_detail_manual.json", ShadeDetail.self),
    .init("bottles.json", BottleGroups.self),
    .init("bottles_archived.json", BottleGroups.self),
    .init("bottles_history.json", History.self),
    .init("wishlist.json", Wishlist.self),
    .init("wheels.json", Wheels.self),
    .init("wheel.json", WheelDetail.self),
    .init("wheel_by_id.json", WheelDetail.self),
    .init("stack_sheet.json", StackSheet.self),
    .init("stack_copy_sources.json", CopySources.self),
    .init("stack_pick.json", Pick.self),
    .init("stack_pick_barcode.json", Pick.self),
    .init("lookup_match.json", Lookup.self),
    .init("lookup_results.json", Lookup.self),
    .init("lookup_unknown_code.json", Lookup.self),
    .init("lookup_short_number.json", Lookup.self),
    .init("lookup_invalid_code.json", Lookup.self),
    .init("identifiers.json", LearnedCodes.self),
    .init("sync.json", SyncStatus.self),
]

@Suite("API fixtures")
struct APIFixtureTests {
    @Test("decodes into its DTO without dropping a key", arguments: getFixtures)
    fileprivate func decodes(_ fixture: GetFixture) throws {
        try fixture.check(fixture.file)
    }

    @Test("every GET fixture of the contract has a decoding test")
    func everyGetFixtureIsCovered() throws {
        let directory = Fixtures.url("api/fixtures")
        let files = try FileManager.default.contentsOfDirectory(atPath: directory.path(percentEncoded: false))
        var uncovered: [String] = []
        for file in files.sorted() where file.hasSuffix(".json") && !file.hasPrefix("error_") {
            let recorded = try recording(file)
            if recorded.method == "GET", !getFixtures.contains(where: { $0.file == file }) { uncovered.append(file) }
        }
        #expect(uncovered.isEmpty, "no DTO test for \(uncovered)")
    }

    @Test("the exchange response decodes")
    func exchangeResponse() throws {
        let recorded = try recording("auth_exchange.json")
        let response = try APICoding.makeDecoder().decode(ExchangeResponse.self, from: recorded.bodyData)
        #expect(response.tokenId == 1)
        #expect(response.user.sub == "u-nikola")
    }

    @Test("a shade row keeps its marks, status and tip")
    func shadeRowFields() throws {
        let page = try APICoding.makeDecoder().decode(ShadePage.self, from: recording("shades_search.json").bodyData)
        let first = try #require(page.items.first)
        #expect(first.title == "Magnetic Taco")
        #expect(first.marks == [[0, 8], [9, 13]])
        #expect(first.status?.key == "available")
        #expect(first.tip.finishes == ["magnetic"])
        #expect(page.fuzzy)
    }
}

@Suite("API errors")
struct APIErrorTests {
    private func error(_ file: String) throws -> APIError {
        let root = try #require(try Fixtures.json("api/fixtures/\(file)") as? [String: Any])
        let payload = try #require(root["body"])
        let status = try #require(root["status"] as? Int)
        return APIError.from(status: status, body: try JSONSerialization.data(withJSONObject: payload))
    }

    @Test func unauthorized() throws { #expect(try error("error_unauthorized.json") == .unauthorized) }
    @Test func notFound() throws { #expect(try error("error_not_found.json") == .notFound) }

    @Test func cooldown() throws {
        guard case .cooldown(let seconds, let message) = try error("error_cooldown.json") else {
            Issue.record("not a cooldown")
            return
        }
        #expect(seconds == 3600)
        #expect(message.contains("61 min"))
    }

    @Test func validation() throws {
        guard case .validation(let field, _, let fields) = try error("error_validation.json") else {
            Issue.record("not a validation error")
            return
        }
        #expect(field == "page")
        #expect(fields["page"] != nil)
    }

    @Test func ruleCodes() throws {
        #expect(try error("error_same_wheel.json") == .rule(code: "same_wheel", message: "A wheel cannot take its own tag."))
        guard case .rule(let code, _) = try error("error_stack_full.json") else { Issue.record("not a rule"); return }
        #expect(code == "stack_full")
        guard case .rule(let empty, _) = try error("error_empty_stack.json") else { Issue.record("not a rule"); return }
        #expect(empty == "empty_stack")
    }

    @Test func conflict() throws {
        guard case .conflict(let code, _) = try error("error_not_a_draft.json") else { Issue.record("not a conflict"); return }
        #expect(code == "not_a_draft")
    }

    @Test func unreadableBodyStillMapsByStatus() {
        #expect(APIError.from(status: 502, body: Data("<html>".utf8)) == .server(status: 502))
        #expect(APIError.from(status: 404, body: Data()) == .notFound)
    }
}

@Suite("Endpoints")
struct EndpointTests {
    @Test func keysAreStableAndOmitDefaults() {
        #expect(Endpoint<Home>.home().key == "/api/v1/home")
        #expect(Endpoint<Home>.home(another: true).key == "/api/v1/home?another=1")
        #expect(Endpoint<ShadePage>.shades(ShadeQuery()).key == "/api/v1/shades")
    }

    @Test func shadeQueryEncodesFiltersInOrder() {
        var query = ShadeQuery()
        query.q = " magentic taco "
        query.finish = ["holographic", "glitter"]
        query.owned = "owned"
        query.sort = "newest"
        query.page = 2
        #expect(
            Endpoint<ShadePage>.shades(query).key
                == "/api/v1/shades?q=magentic%20taco&finish=glitter&finish=holographic&sort=newest&owned=owned&page=2")
        #expect(query.filterCount == 3)
    }
}
