import Foundation
import PolishedModels

/// One write of the contract: the method, the path, the JSON body and what the answer decodes to.
/// `Endpoint` names the GETs; the writes are named here, so a screen, the coordinator and the
/// fixture tests spell a write the same way.
public struct Request<Response: Decodable & Sendable>: Sendable {
    public var method: String
    public var path: String
    /// The encoded JSON body; nil for a request without one.
    public var body: Data?

    public init(_ method: String, _ path: String, body: Data? = nil) {
        self.method = method
        self.path = path
        self.body = body
    }
}

/// A request with `payload` as its JSON body. Encoding the contract's DTOs cannot fail: they hold
/// strings, integers and booleans.
private func make<Response>(_ method: String, _ path: String, _ payload: some Encodable) -> Request<Response> {
    Request(method, path, body: try? APICoding.makeEncoder().encode(payload))
}

/// Every write endpoint the app uses (docs/NATIVE.md 3).
extension Request {
    // Bottles
    public static func addBottle(shadeID: Int, _ bottle: BottleRequest) -> Request<BottleCreated> {
        make("POST", "/api/v1/shades/\(shadeID)/bottles", bottle)
    }

    public static func updateBottle(id: Int, _ patch: BottlePatch) -> Request<Bottle> {
        make("PATCH", "/api/v1/bottles/\(id)", patch)
    }

    public static func deleteBottle(id: Int) -> Request<NoContent> {
        Request<NoContent>("DELETE", "/api/v1/bottles/\(id)")
    }

    // Wishlist
    public static func wish(shadeID: Int, priority: Int = 2) -> Request<WishlistItem> {
        make("PUT", "/api/v1/shades/\(shadeID)/wishlist", WishlistAdd(priority: priority))
    }

    public static func updateWish(id: Int, _ patch: WishlistPatch) -> Request<Wishlist> {
        make("PATCH", "/api/v1/wishlist/\(id)", patch)
    }

    public static func removeWish(id: Int) -> Request<NoContent> {
        Request<NoContent>("DELETE", "/api/v1/wishlist/\(id)")
    }

    public static func bought(_ bought: BoughtRequest) -> Request<Bought> {
        make("POST", "/api/v1/wishlist/bought", bought)
    }

    // Shades
    public static func createShade(_ shade: ManualShadeRequest) -> Request<ShadeDetail> {
        make("POST", "/api/v1/shades", shade)
    }

    public static func setTipColour(shadeID: Int, hex: String?) -> Request<ShadeDetail> {
        make("PUT", "/api/v1/shades/\(shadeID)/tip-colour", TipColourRequest(hex: hex))
    }

    public static func wear(shadeID: Int) -> Request<WearRecorded> {
        Request<WearRecorded>("POST", "/api/v1/wear/\(shadeID)")
    }

    // Wheels
    public static func createWheel(_ wheel: WheelRequest) -> Request<Wheel> {
        make("POST", "/api/v1/wheels", wheel)
    }

    public static func updateWheel(id: Int, _ patch: WheelPatch) -> Request<Wheel> {
        make("PATCH", "/api/v1/wheels/\(id)", patch)
    }

    public static func deleteWheel(id: Int) -> Request<WheelDeleted> {
        Request<WheelDeleted>("DELETE", "/api/v1/wheels/\(id)")
    }

    public static func regenerateTag(wheelID: Int) -> Request<Wheel> {
        Request<Wheel>("POST", "/api/v1/wheels/\(wheelID)/slug/regenerate")
    }

    public static func takeTag(wheelID: Int, from otherID: Int) -> Request<Wheel> {
        make("POST", "/api/v1/wheels/\(wheelID)/slug/take", TakeTagRequest(fromWheelId: otherID))
    }

    // The builder: a slot's draft and the stack being built
    public static func openDraft(wheelID: Int, position: Int) -> Request<StackSheet> {
        Request<StackSheet>("POST", "/api/v1/wheels/\(wheelID)/slots/\(position)/draft")
    }

    public static func clearSlot(wheelID: Int, position: Int) -> Request<NoContent> {
        Request<NoContent>("DELETE", "/api/v1/wheels/\(wheelID)/slots/\(position)")
    }

    public static func addLayer(stackID: Int, shadeID: Int) -> Request<StackSheet> {
        make("POST", "/api/v1/stacks/\(stackID)/layers", LayerRequest(shadeId: shadeID))
    }

    public static func changeCoats(stackID: Int, layerID: Int, delta: Int) -> Request<StackSheet> {
        make("PATCH", "/api/v1/stacks/\(stackID)/layers/\(layerID)", LayerPatch(coatsDelta: delta))
    }

    public static func moveLayer(stackID: Int, layerID: Int, direction: String) -> Request<StackSheet> {
        make("PATCH", "/api/v1/stacks/\(stackID)/layers/\(layerID)", LayerPatch(move: direction))
    }

    public static func removeLayer(stackID: Int, layerID: Int) -> Request<StackSheet> {
        Request<StackSheet>("DELETE", "/api/v1/stacks/\(stackID)/layers/\(layerID)")
    }

    public static func template(stackID: Int, _ template: TemplateRequest) -> Request<StackSheet> {
        make("POST", "/api/v1/stacks/\(stackID)/template", template)
    }

    public static func saveStack(stackID: Int, _ stack: SaveStackRequest) -> Request<SlotResult> {
        make("POST", "/api/v1/stacks/\(stackID)/save", stack)
    }

    public static func cancelStack(stackID: Int) -> Request<SlotResult> {
        Request<SlotResult>("POST", "/api/v1/stacks/\(stackID)/cancel")
    }

    // Codes
    public static func learn(_ code: LearnRequest) -> Request<IdentifierSaved> {
        make("POST", "/api/v1/identifiers", code)
    }

    public static func forgetCode(id: Int) -> Request<NoContent> {
        Request<NoContent>("DELETE", "/api/v1/identifiers/\(id)")
    }

    // Sync
    public static func runSync() -> Request<SyncStarted> {
        Request<SyncStarted>("POST", "/api/v1/sync/run")
    }
}
