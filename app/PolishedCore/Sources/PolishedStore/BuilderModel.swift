import Foundation
import Observation
import PolishedAPI
import PolishedModels

/// Which shades the builder's picker offers (`GET /stacks/pick?scope=`).
public enum PickScope: String, Sendable, CaseIterable, Identifiable {
    case owned, toppers, all

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .owned: "Owned"
        case .toppers: "Toppers"
        case .all: "All"
        }
    }
}

/// The layer builder for one slot (docs/NATIVE.md 5.2, docs/DESIGN.md 10): the draft stack the
/// server holds, and the picker that adds to it. Coats, moves and removals apply at once and are
/// sent in order; the server's answer replaces the sheet only when no edit is still waiting, so
/// three quick taps on + never bounce back to the first answer. Adding a layer and the three
/// templates wait for the server (a new layer's id is the server's).
@MainActor
@Observable
public final class BuilderModel {
    public static let maxLayers = 8
    public static let minCoats = 1
    public static let maxCoats = 5

    public let wheelID: Int
    public let position: Int
    /// The swatch being built; nil until the draft is open.
    public private(set) var sheet: StackSheet?
    /// The draft was there already ("Resumed your draft").
    public private(set) var resumed = false
    /// Why the draft could not be opened.
    public private(set) var openError: APIError?
    /// A sentence under the layers: a refused edit, or what a template found.
    public private(set) var notice: String?
    /// The shade whose + is waiting for the server.
    public private(set) var adding: Int?

    /// Haptic triggers (docs/NATIVE.md 5.8): a layer or a coat changed, an edit was refused, the
    /// server said "nothing" to a template.
    public private(set) var edits = 0
    public private(set) var failures = 0
    public private(set) var warnings = 0

    // The picker
    public var query = ""
    public var scope = PickScope.owned
    public private(set) var pick: Pick?
    public private(set) var pickFailed = false

    @ObservationIgnored private let api: any PolishedAPI
    @ObservationIgnored private let writes: WriteCoordinator
    @ObservationIgnored private var waiting = 0
    @ObservationIgnored private var tail: Task<Void, Never>?
    @ObservationIgnored private var opening: Task<Void, Never>?

    public init(wheelID: Int, position: Int, api: any PolishedAPI, writes: WriteCoordinator) {
        self.wheelID = wheelID
        self.position = position
        self.api = api
        self.writes = writes
    }

    public var layers: [Layer] { sheet?.layers ?? [] }
    public var isFull: Bool { layers.count >= Self.maxLayers }
    public var canSave: Bool { !layers.isEmpty }

    // MARK: Opening

    /// Opens the slot's draft: the saved layers copied, or the draft that was left there.
    public func open() async {
        guard sheet == nil else { return }
        // Two views asking at once share one request: a second POST would answer "resumed".
        if let opening {
            await opening.value
            return
        }
        openError = nil
        let task = Task { @MainActor [self] in
            do {
                let opened = try await writes.perform(.openDraft(wheelID: wheelID, position: position), affecting: .wheels)
                sheet = opened
                resumed = opened.resumed ?? false
            } catch let error as APIError {
                openError = error
            } catch {
                openError = .offline
            }
            opening = nil
        }
        opening = task
        await task.value
    }

    // MARK: Layers

    /// Paints `shade` on top. Waits for the server; the answer is the new sheet.
    public func add(_ shade: ShadeRow) {
        guard let sheet, adding == nil else { return }
        guard !isFull else {
            refuse("A swatch holds up to \(Self.maxLayers) layers.")
            return
        }
        notice = nil
        adding = shade.id
        enqueue { [self] in
            defer { adding = nil }
            await send(.addLayer(stackID: sheet.stackId, shadeID: shade.id), edit: nil)
            // Back to the owned shades, ready for the next layer (the web does the same).
            query = ""
        }
    }

    /// A coat more or less, 1 to 5.
    public func changeCoats(of layer: Layer, by delta: Int) {
        guard let sheet, let index = sheet.layers.firstIndex(where: { $0.id == layer.id }) else { return }
        let coats = sheet.layers[index].coats + delta
        guard (Self.minCoats...Self.maxCoats).contains(coats) else { return }
        notice = nil
        let stackID = sheet.stackId
        apply { $0.layers[index].coats = coats; $0.layers[index].tip.coats = coats }
        enqueue { [self] in await send(.changeCoats(stackID: stackID, layerID: layer.id, delta: delta), edit: true) }
    }

    /// One place towards the base (`up`) or the top (`down`).
    public func move(_ layer: Layer, up: Bool) {
        guard let sheet, let index = sheet.layers.firstIndex(where: { $0.id == layer.id }) else { return }
        let other = up ? index - 1 : index + 1
        guard sheet.layers.indices.contains(other) else { return }
        notice = nil
        let stackID = sheet.stackId
        apply { $0.layers.swapAt(index, other) }
        enqueue { [self] in
            await send(.moveLayer(stackID: stackID, layerID: layer.id, direction: up ? "up" : "down"), edit: true)
        }
    }

    public func remove(_ layer: Layer) {
        guard let sheet else { return }
        notice = nil
        let stackID = sheet.stackId
        apply { $0.layers.removeAll { $0.id == layer.id } }
        enqueue { [self] in await send(.removeLayer(stackID: stackID, layerID: layer.id), edit: true) }
    }

    // MARK: Templates

    public func overBlack() {
        template(TemplateRequest(kind: "over_black"))
    }

    public func copy(from source: CopySource) {
        template(TemplateRequest(kind: "copy", sourceStackId: source.stackId))
    }

    public func sameAsLast() {
        template(TemplateRequest(kind: "last"))
    }

    private func template(_ template: TemplateRequest) {
        guard let sheet else { return }
        notice = nil
        enqueue { [self] in
            await send(.template(stackID: sheet.stackId, template), edit: nil) { [self] answer in
                switch answer.result {
                case "already": notice = "Already over black."
                case "unavailable": notice = "Over black isn\u{2019}t in the catalog."
                case "nothing_saved":
                    notice = "Nothing is saved on a wheel yet."
                    warnings += 1
                default: break
                }
            }
        }
    }

    public func clearNotice() { notice = nil }

    // MARK: Leaving

    /// Saves the swatch: every edit still on its way goes first. Throws the server's refusal
    /// (`empty_stack`, a `validation` on `painted_on`).
    public func save(name: String, note: String, paintedOn: String?) async throws -> SlotResult {
        await settle()
        guard let sheet else { throw APIError.notFound }
        return try await writes.perform(
            .saveStack(stackID: sheet.stackId, SaveStackRequest(name: name, note: note, paintedOn: paintedOn)),
            affecting: .wheelChange)
    }

    /// Throws the draft away; the slot keeps its saved swatch.
    public func cancel() async throws -> SlotResult {
        await settle()
        guard let sheet else { throw APIError.notFound }
        return try await writes.perform(.cancelStack(stackID: sheet.stackId), affecting: .wheels)
    }

    /// Removes the saved swatch of the slot, and any draft with it.
    public func clearSlot() async throws {
        await settle()
        _ = try await writes.perform(.clearSlot(wheelID: wheelID, position: position), affecting: .wheelChange)
    }

    // MARK: The picker

    /// Loads the rows for `query` and `scope`; a failure keeps the rows that were there.
    public func refreshPicker() async {
        let words = query.trimmingCharacters(in: .whitespaces)
        do {
            let loaded = try await api.get(.pick(q: words, scope: scope.rawValue))
            guard words == query.trimmingCharacters(in: .whitespaces) else { return }
            pick = loaded
            pickFailed = false
        } catch is CancellationError {
        } catch {
            pickFailed = true
        }
    }

    public func copySources(matching words: String) async -> CopySources? {
        try? await api.get(.copySources(q: words.trimmingCharacters(in: .whitespaces)))
    }

    // MARK: Plumbing

    private func refuse(_ message: String) {
        notice = message
        failures += 1
    }

    /// Changes the sheet now (the server's answer follows).
    private func apply(_ change: (inout StackSheet) -> Void) {
        guard var local = sheet else { return }
        change(&local)
        local.layers = Self.relabelled(local.layers)
        local.summary = Self.summary(of: local.layers)
        local.tip = local.layers.map(\.tip)
        local.full = local.layers.count >= Self.maxLayers
        sheet = local
        edits += 1
    }

    private func enqueue(_ work: @escaping @MainActor () async -> Void) {
        waiting += 1
        let earlier = tail
        tail = Task { @MainActor [self] in
            await earlier?.value
            await work()
            waiting -= 1
        }
    }

    /// Waits for every queued edit.
    private func settle() async {
        await tail?.value
    }

    /// Sends one edit. `edit` is true for an edit that was applied already (a failure reloads the
    /// sheet from the server) and nil for one that waits for the answer.
    private func send(_ request: Request<StackSheet>, edit: Bool?, then: (StackSheet) -> Void = { _ in }) async {
        do {
            let answer = try await api.send(request)
            // Later edits are already on the screen; the last answer is the one that counts.
            if waiting <= 1 {
                sheet = answer
                if edit == nil { edits += 1 }
            }
            then(answer)
        } catch {
            failures += 1
            notice = Self.sentence(for: error)
            if waiting <= 1, let id = sheet?.stackId, let reloaded = try? await api.get(.stack(id: id)) {
                sheet = reloaded
            }
        }
    }

    private static func sentence(for error: Error) -> String {
        guard let error = error as? APIError else { return APIError.offline.message }
        if case .conflict = error { return "This swatch is no longer being edited. Close it and open the slot again." }
        return error.message
    }

    // MARK: What the server computes, for the moment before it answers

    /// None for one layer, then Base, 2nd, 3rd, ..., Top.
    public static func labels(count: Int) -> [String] {
        guard count > 1 else { return Array(repeating: "", count: count) }
        let middle = (2..<max(count, 2)).map { number in "\(number)\(number == 2 ? "nd" : number == 3 ? "rd" : "th")" }
        return ["Base"] + middle + ["Top"]
    }

    static func relabelled(_ layers: [Layer]) -> [Layer] {
        let labels = labels(count: layers.count)
        return layers.enumerated().map { index, layer in
            var layer = layer
            layer.ord = index + 1
            layer.label = labels[index]
            return layer
        }
    }

    /// "One-Coat Black + Spirit Fingers ×2 + Flakie Holo Taco".
    public static func summary(of layers: [Layer]) -> String {
        layers.map { $0.coats > 1 ? "\($0.title) ×\($0.coats)" : $0.title }.joined(separator: " + ")
    }
}
