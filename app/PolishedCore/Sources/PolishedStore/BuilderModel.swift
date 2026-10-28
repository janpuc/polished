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

/// What the wheel page already has of the slot, to open the builder on before the server answers:
/// the wheel and the slot's tile (the saved layers, which a new draft copies).
public struct BuilderPreview: Sendable {
    public var wheel: StackWheel
    public var tile: Tile

    public init(wheel: StackWheel, tile: Tile) {
        self.wheel = wheel
        self.tile = tile
    }
}

/// Keeps the picker's last answer per scope while the app runs, so a builder opened again shows the
/// shades at once and refreshes them quietly (the response cache is emptied by every wheel write,
/// opening a draft included). Only the unsearched list is kept.
@MainActor
public final class PickMemory {
    private var picks: [PickScope: Pick] = [:]

    public init() {}

    public subscript(scope: PickScope) -> Pick? {
        get { picks[scope] }
        set { picks[scope] = newValue }
    }
}

/// The layer builder for one slot (docs/NATIVE.md 5.2, docs/DESIGN.md 10): the draft stack the
/// server holds, and the picker that adds to it. The builder opens on the slot's saved layers from
/// the wheel page while the draft is being opened; every edit (a new layer, a coat, a move, a
/// removal) applies at once and is sent in order once the draft is known, and the server's answer
/// replaces the sheet only when no edit is still waiting, so three quick taps on + never bounce back
/// to the first answer. The three templates wait for the server (it computes what they add).
@MainActor
@Observable
public final class BuilderModel {
    public static let maxLayers = 8
    public static let minCoats = 1
    public static let maxCoats = 5

    public let wheelID: Int
    public let position: Int
    /// The swatch being built: the slot's saved layers until the draft answers (nil for a slot that
    /// has a draft already, whose layers only the server knows).
    public private(set) var sheet: StackSheet?
    /// The server's stack id of the draft; nil until the draft is open.
    public private(set) var draftID: Int?
    /// The draft was there already ("Resumed your draft").
    public private(set) var resumed = false
    /// The background cancel of `discard()`: the slot opened again waits for it, or the draft it
    /// opens would be the one being thrown away.
    @ObservationIgnored public private(set) var discarding: Task<Void, Never>?
    /// Why the draft could not be opened.
    public private(set) var openError: APIError?
    /// A sentence under the layers: a refused edit, or what a template found.
    public private(set) var notice: String?

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
    @ObservationIgnored private let memory: PickMemory
    @ObservationIgnored private var waiting = 0
    @ObservationIgnored private var tail: Task<Void, Never>?
    @ObservationIgnored private var opening: Task<Void, Never>?
    /// Bumped when the queued edits no longer fit the draft; edits queued before it are dropped.
    @ObservationIgnored private var epoch = 0
    /// The ids the sheet shows that are not the draft's yet: the saved layers' (the draft copies
    /// them) and the layers added before their answer.
    @ObservationIgnored private var draftIDs: [Int: Int] = [:]
    @ObservationIgnored private var previewIDs: [Int] = []
    @ObservationIgnored private var provisionalCount = 0

    public init(
        wheelID: Int, position: Int, api: any PolishedAPI, writes: WriteCoordinator,
        preview: BuilderPreview? = nil, pickMemory: PickMemory = PickMemory(), after earlier: Task<Void, Never>? = nil
    ) {
        self.wheelID = wheelID
        self.position = position
        self.api = api
        self.writes = writes
        memory = pickMemory
        // A cancelled builder's draft is thrown away first (`discard()`), or this one would open it.
        tail = earlier
        pick = pickMemory[.owned]
        // A slot with a draft shows the draft's layers, which the tile does not carry.
        if let preview, !preview.tile.hasDraft {
            let layers = preview.tile.layers
            previewIDs = layers.map(\.id)
            sheet = StackSheet(
                stackId: preview.tile.stackId ?? 0, wheel: preview.wheel, position: position, layers: layers,
                summary: Self.summary(of: layers), full: layers.count >= Self.maxLayers, tip: layers.map(\.tip))
        }
    }

    public var layers: [Layer] { sheet?.layers ?? [] }
    public var isFull: Bool { layers.count >= Self.maxLayers }
    public var canSave: Bool { !layers.isEmpty }

    // MARK: Opening

    /// Opens the slot's draft: the saved layers copied, or the draft that was left there. The sheet
    /// shows the saved layers meanwhile and edits wait in the queue; returns when the answer is in.
    public func open() async {
        // Two views asking at once share one request: a second POST would answer "resumed".
        if opening == nil, draftID == nil {
            openError = nil
            opening = enqueue(always: true) { [self] in
                await openDraft()
                opening = nil
            }
        }
        await opening?.value
    }

    private func openDraft() async {
        do {
            let opened = try await writes.perform(.openDraft(wheelID: wheelID, position: position), affecting: .wheels)
            take(opened)
        } catch {
            openError = error as? APIError ?? .offline
            // Nothing queued behind it can be sent; the retry opens the sheet from the server.
            epoch += 1
            sheet = nil
        }
    }

    /// The draft's answer: its id for the edits behind it, and its layers if nothing is waiting on
    /// the sheet.
    private func take(_ opened: StackSheet) {
        draftID = opened.stackId
        resumed = opened.resumed ?? false
        let showsSaved = !previewIDs.isEmpty || sheet != nil
        // A draft that was there already (another phone) has other layers than the ones shown.
        let differs = showsSaved && (resumed || opened.layers.count != previewIDs.count)
        if !differs {
            for (shown, real) in zip(previewIDs, opened.layers.map(\.id)) { draftIDs[shown] = real }
        }
        if waiting <= 1 || differs || sheet == nil {
            if differs, waiting > 1 {
                epoch += 1
                notice = "This swatch had a draft already. Your first taps were not applied."
            }
            sheet = opened
        } else {
            sheet?.stackId = opened.stackId
            sheet?.name = opened.name
            sheet?.note = opened.note
            sheet?.paintedOn = opened.paintedOn
        }
        previewIDs = []
    }

    // MARK: Layers

    /// Paints `shade` on top at once; the server's answer follows.
    public func add(_ shade: ShadeRow) {
        guard sheet != nil else { return }
        guard !isFull else {
            refuse("A swatch holds up to \(Self.maxLayers) layers.")
            return
        }
        notice = nil
        provisionalCount += 1
        var tip = shade.tip
        tip.coats = 1
        let provisional = Layer(
            id: -provisionalCount, ord: 0, shadeId: shade.id, title: shade.title, coats: 1, label: "", tip: tip)
        apply { $0.layers.append(provisional) }
        // Back to the owned shades, ready for the next layer (the web does the same).
        query = ""
        edit({ stackID, _ in Request<StackSheet>.addLayer(stackID: stackID, shadeID: shade.id) }) { [self] answer in
            if let added = answer.layers.last { draftIDs[provisional.id] = added.id }
        }
    }

    /// A coat more or less, 1 to 5.
    public func changeCoats(of layer: Layer, by delta: Int) {
        guard let sheet, let index = sheet.layers.firstIndex(where: { $0.id == layer.id }) else { return }
        let coats = sheet.layers[index].coats + delta
        guard (Self.minCoats...Self.maxCoats).contains(coats) else { return }
        notice = nil
        apply { $0.layers[index].coats = coats; $0.layers[index].tip.coats = coats }
        edit { stackID, serverID in
            serverID(layer.id).map { Request<StackSheet>.changeCoats(stackID: stackID, layerID: $0, delta: delta) }
        }
    }

    /// One place towards the base (`up`) or the top (`down`).
    public func move(_ layer: Layer, up: Bool) {
        guard let sheet, let index = sheet.layers.firstIndex(where: { $0.id == layer.id }) else { return }
        let other = up ? index - 1 : index + 1
        guard sheet.layers.indices.contains(other) else { return }
        notice = nil
        apply { $0.layers.swapAt(index, other) }
        edit { stackID, serverID in
            serverID(layer.id).map {
                Request<StackSheet>.moveLayer(stackID: stackID, layerID: $0, direction: up ? "up" : "down")
            }
        }
    }

    public func remove(_ layer: Layer) {
        guard sheet != nil else { return }
        notice = nil
        apply { $0.layers.removeAll { $0.id == layer.id } }
        edit { stackID, serverID in serverID(layer.id).map { Request<StackSheet>.removeLayer(stackID: stackID, layerID: $0) } }
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
        guard sheet != nil else { return }
        notice = nil
        enqueue { [self] in
            guard let draftID else { return }
            await send(.template(stackID: draftID, template), edit: nil) { [self] answer in
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
        guard let draftID else { throw openError ?? APIError.notFound }
        return try await writes.perform(
            .saveStack(stackID: draftID, SaveStackRequest(name: name, note: note, paintedOn: paintedOn)),
            affecting: .wheelChange)
    }

    /// Throws the draft away; the slot keeps its saved swatch.
    public func cancel() async throws -> SlotResult {
        await settle()
        guard let draftID else { throw openError ?? APIError.notFound }
        return try await writes.perform(.cancelStack(stackID: draftID), affecting: .wheels)
    }

    /// Throws the draft away without keeping the sheet open for the network: the edits still on
    /// their way go first, then the cancel, in the background. A failure is said under the wheel's
    /// title; the draft is then still on the slot ("Resumed your draft.").
    public func discard() {
        discarding = Task { @MainActor [self] in
            await settle()
            guard draftID != nil else { return }
            do {
                _ = try await cancel()
            } catch APIError.notFound, APIError.conflict {
                // The draft is gone already.
            } catch {
                writes.show("Couldn\u{2019}t throw the draft away. It is still on slot \(position).", kind: .failure)
            }
        }
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
        let scope = scope
        // The last list of this scope shows while the new one is on its way.
        if words.isEmpty, let remembered = memory[scope] { pick = remembered }
        do {
            let loaded = try await api.get(.pick(q: words, scope: scope.rawValue))
            if words.isEmpty { memory[scope] = loaded }
            guard words == query.trimmingCharacters(in: .whitespaces), scope == self.scope else { return }
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

    /// Runs `work` after everything queued before it. Work queued before the draft turned out to
    /// differ from the sheet is dropped (`always` keeps the opening itself).
    @discardableResult
    private func enqueue(always: Bool = false, _ work: @escaping @MainActor () async -> Void) -> Task<Void, Never> {
        waiting += 1
        let earlier = tail
        let queuedIn = epoch
        let task = Task { @MainActor [self] in
            await earlier?.value
            if always || queuedIn == epoch { await work() }
            waiting -= 1
        }
        tail = task
        return task
    }

    /// Queues an edit that is on the sheet already. `request` builds it once the draft is known,
    /// with the draft's id for a layer the sheet shows (nil when that layer never reached the draft).
    private func edit(
        _ request: @escaping @MainActor (_ stackID: Int, _ draftLayerID: (Int) -> Int?) -> Request<StackSheet>?,
        then: @escaping @MainActor (StackSheet) -> Void = { _ in }
    ) {
        enqueue { [self] in
            guard let draftID, let built = request(draftID, { [self] in draftLayerID(for: $0) }) else { return }
            await send(built, edit: true, then: then)
        }
    }

    private func draftLayerID(for shown: Int) -> Int? {
        if let real = draftIDs[shown] { return real }
        return shown > 0 ? shown : nil
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
            if waiting <= 1, let id = draftID, let reloaded = try? await api.get(.stack(id: id)) {
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
