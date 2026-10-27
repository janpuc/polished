import Foundation
import PolishedAPI
import PolishedModels
import Testing

/// One write of `spec/api/fixtures/`: the request the app builds must be the one recorded
/// (method, path, JSON body), and the recorded answer must decode into the DTO without dropping
/// a key.
private struct WriteFixture: Sendable, CustomTestStringConvertible {
    var file: String
    var check: @Sendable () throws -> Void
    var testDescription: String { file }

    init<Response: Codable & Sendable>(_ file: String, _ request: Request<Response>) {
        self.file = file
        check = {
            let recorded = try recording(file)
            #expect(request.method == recorded.method, "\(file): method")
            #expect(request.path == recorded.path, "\(file): path")
            if let expected = recorded.requestBody {
                let body = try #require(request.body, "\(file): the request has no body")
                let sent = try JSONSerialization.jsonObject(with: body)
                #expect((sent as? NSDictionary) == (expected as? NSDictionary), "\(file): body \(sent) is not \(expected)")
            } else {
                #expect(request.body == nil, "\(file): the recording has no body")
            }
            guard recorded.status != 204 else { return }
            let value = try APICoding.makeDecoder().decode(Response.self, from: recorded.bodyData)
            let encoded = try JSONSerialization.jsonObject(with: APICoding.makeEncoder().encode(value))
            let dropped = droppedKeys(recorded.body, encoded)
            #expect(dropped.isEmpty, "\(file): the DTO does not carry \(dropped.sorted())")
        }
    }
}

private let writeFixtures: [WriteFixture] = [
    .init(
        "bottle_create.json",
        .addBottle(
            shadeID: 1,
            BottleRequest(
                state: .half, printedCode: "321", boughtOn: "2026-10-20", pricePaidCents: 1550,
                openedOn: "2026-10-24", notes: "From the pop-up"))),
    .init("bottle_create_known_code.json", .addBottle(shadeID: 1, BottleRequest(state: .full, printedCode: "P259"))),
    .init("bottle_update.json", .updateBottle(id: 7, patch)),
    .init("bottle_delete.json", .deleteBottle(id: 7)),
    .init("wishlist_add.json", .wish(shadeID: 1, priority: 2)),
    .init("wishlist_update.json", .updateWish(id: 4, WishlistPatch(priority: .set(1), note: .set("Birthday")))),
    .init("wishlist_remove.json", .removeWish(id: 4)),
    .init(
        "wishlist_bought.json",
        .bought(
            BoughtRequest(
                items: [BoughtItem(id: 1, priceCents: 1550), BoughtItem(id: 2, priceCents: nil)], boughtOn: "2026-10-25"))),
    .init("shade_create.json", .createShade(ManualShadeRequest(title: "Birthday Glitter", kind: "topper"))),
    .init("shade_tip_colour.json", .setTipColour(shadeID: 13, hex: "#7a3fd1")),
    .init("shade_tip_colour_reset.json", .setTipColour(shadeID: 13, hex: nil)),
    .init("wear_record.json", .wear(shadeID: 13)),
    .init("wheel_create.json", .createWheel(WheelRequest(name: "Jellies", slotCount: 12))),
    .init("wheel_update.json", .updateWheel(id: 3, WheelPatch(name: .set("Jelly wheel")))),
    .init("wheel_delete.json", .deleteWheel(id: 3)),
    .init("wheel_slug_regenerate.json", .regenerateTag(wheelID: 3)),
    .init("wheel_slug_take.json", .takeTag(wheelID: 3, from: 2)),
    .init("sync_run.json", .runSync()),
    .init("slot_draft.json", .openDraft(wheelID: 3, position: 3)),
    .init("slot_draft_new.json", .openDraft(wheelID: 3, position: 4)),
    .init("slot_draft_resumed.json", .openDraft(wheelID: 3, position: 3)),
    .init("slot_clear.json", .clearSlot(wheelID: 3, position: 3)),
    .init("layer_add.json", .addLayer(stackID: 4, shadeID: 1)),
    .init("layer_add_second.json", .addLayer(stackID: 4, shadeID: 14)),
    .init("layer_coats.json", .changeCoats(stackID: 4, layerID: 6, delta: 1)),
    .init("layer_move.json", .moveLayer(stackID: 4, layerID: 6, direction: "down")),
    .init("layer_delete.json", .removeLayer(stackID: 4, layerID: 6)),
    .init("stack_template_over_black.json", .template(stackID: 4, TemplateRequest(kind: "over_black"))),
    .init("stack_template_copy.json", .template(stackID: 4, TemplateRequest(kind: "copy", sourceStackId: 1))),
    .init("stack_template_last.json", .template(stackID: 4, TemplateRequest(kind: "last"))),
    .init(
        "stack_save.json",
        .saveStack(stackID: 4, SaveStackRequest(name: "Black and flakes", note: "Dried fast", paintedOn: "2026-10-25"))),
    .init("stack_cancel.json", .cancelStack(stackID: 5)),
]

private var patch: BottlePatch {
    var patch = BottlePatch()
    patch.state = .set(.low)
    patch.notes = .clear
    patch.archived = .set(false)
    return patch
}

/// The write fixtures that belong to the codes (run 5) and the sign-in.
private let laterFixtures: Set<String> = ["auth_exchange.json", "identifier_forget.json", "identifier_learn.json"]

@Suite("Write fixtures")
struct WriteFixtureTests {
    @Test("the request is the recorded one and the answer decodes", arguments: writeFixtures)
    fileprivate func matches(_ fixture: WriteFixture) throws {
        try fixture.check()
    }

    @Test("every write fixture has a test, or belongs to a later run")
    func everyWriteFixtureIsCovered() throws {
        let directory = Fixtures.url("api/fixtures")
        let files = try FileManager.default.contentsOfDirectory(atPath: directory.path(percentEncoded: false))
        var uncovered: [String] = []
        for file in files.sorted() where file.hasSuffix(".json") && !file.hasPrefix("error_") {
            let recorded = try recording(file)
            if recorded.method != "GET", !writeFixtures.contains(where: { $0.file == file }), !laterFixtures.contains(file) {
                uncovered.append(file)
            }
        }
        #expect(uncovered.isEmpty, "no test for \(uncovered)")
    }

    @Test("a bottle PATCH sends only what changed, null clears")
    func patchKeepsAndClears() throws {
        var change = BottlePatch()
        change.state = .set(.empty)
        change.notes = .clear
        let request = Request<Bottle>.updateBottle(id: 3, change)
        let data = try #require(request.body)
        let body = try #require(JSONSerialization.jsonObject(with: data) as? NSDictionary)
        #expect(body == ["state": "empty", "notes": NSNull()])
        #expect(Request<Bottle>.updateBottle(id: 3, BottlePatch()).body.map { String(decoding: $0, as: UTF8.self) } == "{}")
    }

    @Test("a created bottle says what was learned")
    func learnedCodes() throws {
        let fresh = try APICoding.makeDecoder().decode(BottleCreated.self, from: recording("bottle_create.json").bodyData)
        #expect(fresh.learned?.code == "P321")
        #expect(fresh.learned?.previousShade == nil)
        let known = try APICoding.makeDecoder().decode(BottleCreated.self, from: recording("bottle_create_known_code.json").bodyData)
        #expect(known.learned?.previousShade?.title == "Spirit Fingers")
    }

    @Test("a 422 lists every wrong field")
    func validationFields() throws {
        let recorded = try recording("error_validation_bottle.json")
        guard case .validation(let field, _, let fields) = APIError.from(status: recorded.status, body: recorded.bodyData) else {
            Issue.record("not a validation error")
            return
        }
        #expect(field == "state")
        #expect(Set(fields.keys) == ["state", "bought_on", "price_paid_cents"])
        #expect(fields["price_paid_cents"] == "Use an amount like 15.50.")
    }
}

@Suite("FixtureAPI writes")
struct FixtureAPIWriteTests {
    private func api() throws -> FixtureAPI {
        try FixtureAPI(directory: Fixtures.url("api/fixtures"))
    }

    @Test func answersAWriteFromItsRecording() async throws {
        let created = try await api().send(.addBottle(shadeID: 1, BottleRequest(state: .half)))
        #expect(created.bottle.id == 7)
        let wheel = try await api().send(.createWheel(WheelRequest(name: "x")))
        #expect(wheel.slug == "j7g2hm")
        let none = try await api().send(.deleteBottle(id: 7))
        #expect(none == NoContent())
    }

    @Test func aWriteWithoutARecordingIsNotFound() async throws {
        await #expect(throws: APIError.notFound) { try await api().send(.deleteBottle(id: 999)) }
    }
}
