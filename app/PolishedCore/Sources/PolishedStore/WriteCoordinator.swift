import Foundation
import Observation
import PolishedAPI
import PolishedModels

/// The snapshots a write makes stale, by the start of their key (`Endpoint.key`).
public struct WriteEffect: OptionSet, Sendable {
    public let rawValue: Int

    public init(rawValue: Int) {
        self.rawValue = rawValue
    }

    public static let home = WriteEffect(rawValue: 1 << 0)
    /// The shade list and every shade's page: ownership, hearts and tips show in both.
    public static let shades = WriteEffect(rawValue: 1 << 1)
    public static let bottles = WriteEffect(rawValue: 1 << 2)
    public static let wishlist = WriteEffect(rawValue: 1 << 3)
    public static let wheels = WriteEffect(rawValue: 1 << 4)
    public static let sync = WriteEffect(rawValue: 1 << 5)

    /// A bottle added, changed or deleted: Home's numbers and rack, the lists, the shade's page,
    /// the wishlist rows (they carry the owned count).
    public static let bottleChange: WriteEffect = [.home, .shades, .bottles, .wishlist]
    public static let wishlistChange: WriteEffect = [.home, .shades, .wishlist]
    /// A new shade by hand.
    public static let shadeChange: WriteEffect = [.home, .shades]
    /// A tip colour is drawn on every screen that has the shade.
    public static let tipColour: WriteEffect = [.home, .shades, .bottles, .wishlist, .wheels]
    public static let wear: WriteEffect = [.home]
    /// A wheel made, renamed, archived, deleted or re-tagged; a shade's "Swatched on" names it.
    public static let wheelChange: WriteEffect = [.home, .shades, .wheels]
    public static let syncStarted: WriteEffect = [.home, .shades, .sync]

    var prefixes: [String] {
        var keys: [String] = []
        if contains(.home) { keys.append("/api/v1/home") }
        if contains(.shades) { keys.append("/api/v1/shades") }
        if contains(.bottles) { keys += ["/api/v1/bottles", "/api/v1/stacks/pick"] }
        if contains(.wishlist) { keys.append("/api/v1/wishlist") }
        if contains(.wheels) { keys += ["/api/v1/wheels", "/api/v1/w/", "/api/v1/stacks"] }
        if contains(.sync) { keys.append("/api/v1/sync") }
        return keys
    }
}

/// The line the person reads after a write: a failed toggle that was undone, or a fact the server
/// told ("Learned P321").
public struct StatusLine: Sendable, Equatable, Identifiable {
    public enum Kind: Sendable { case info, warning, failure }

    public let id: Int
    public let message: String
    public let kind: Kind

    public var isFailure: Bool { kind == .failure }
}

/// Every write goes through here (docs/NATIVE.md 2.3). The four toggles (the wishlist heart, a
/// priority, a bottle's level, "I wore this") apply their result at once, send the request, and on
/// a failure put things back and say so, with one retry after two seconds when the request timed
/// out. Everything else awaits the server (`perform`), with the progress state of `SaveAction`.
/// There is no queue and no offline write. A write that went through forgets the snapshots it
/// made stale and raises `revision`, which the screens reload on.
@MainActor
@Observable
public final class WriteCoordinator {
    /// Raised after every write that changed something, or tried to; the screens reload on it.
    public private(set) var revision = 0
    public private(set) var status: StatusLine?
    /// How many toggles had to be undone (the haptic trigger).
    public private(set) var failures = 0
    /// How many times the server told something the person should notice (the haptic trigger).
    public private(set) var warnings = 0

    @ObservationIgnored private let api: any PolishedAPI
    @ObservationIgnored private let cache: (any ResponseCache)?
    @ObservationIgnored private let retryDelay: Duration
    @ObservationIgnored private var lanes: [String: Task<Void, Never>] = [:]
    @ObservationIgnored private var statusTask: Task<Void, Never>?
    @ObservationIgnored private var statusCount = 0

    public init(api: any PolishedAPI, cache: (any ResponseCache)? = nil, retryDelay: Duration = .seconds(2)) {
        self.api = api
        self.cache = cache
        self.retryDelay = retryDelay
    }

    /// A write that waits for the server's answer. Throws the server's error; nothing changed then.
    public func perform<Response: Decodable & Sendable>(
        _ request: Request<Response>, affecting effect: WriteEffect
    ) async throws -> Response {
        let response = try await api.send(request)
        await didWrite(effect)
        return response
    }

    /// An optimistic toggle. `apply` runs now; `revert` runs if the write fails, and `failure`
    /// becomes the status line ("Couldn't save. Still half."). Toggles of one `lane` (one bottle,
    /// one shade) are sent in the order they were made. Returns the response, or nil when it failed.
    @discardableResult
    public func toggle<Response: Decodable & Sendable>(
        lane: String,
        _ request: Request<Response>,
        affecting effect: WriteEffect,
        failure message: String,
        apply: @MainActor @Sendable () -> Void,
        revert: @escaping @MainActor @Sendable () -> Void,
        onSuccess: @escaping @MainActor @Sendable (Response) -> Void = { _ in }
    ) async -> Response? {
        await toggle(
            lane: lane, affecting: effect, failure: message, apply: apply, revert: revert, onSuccess: onSuccess,
            send: { api in try await api.send(request) })
    }

    /// The same toggle for a write that needs the API first (it looks something up, then sends).
    @discardableResult
    public func toggle<Response: Sendable>(
        lane: String,
        affecting effect: WriteEffect,
        failure message: String,
        apply: @MainActor @Sendable () -> Void,
        revert: @escaping @MainActor @Sendable () -> Void,
        onSuccess: @escaping @MainActor @Sendable (Response) -> Void = { _ in },
        send operation: @escaping @Sendable (any PolishedAPI) async throws -> Response
    ) async -> Response? {
        apply()
        let earlier = lanes[lane]
        let task = Task { @MainActor [self] () -> Response? in
            await earlier?.value
            do {
                let response = try await retryingTimeout(operation)
                onSuccess(response)
                await didWrite(effect)
                return response
            } catch is CancellationError {
                return nil
            } catch {
                revert()
                failures += 1
                if (error as? APIError) != .unauthorized { show(message, kind: .failure) }
                revision += 1
                return nil
            }
        }
        lanes[lane] = Task { _ = await task.value }
        return await task.value
    }

    /// A bottle's level, the toggle every list and sheet shares. `edit` changes that bottle in the
    /// caller's data (`edit(id) { $0.state = .half }`), now and again to put it back.
    public func changeLevel(
        _ bottle: Bottle, to level: BottleState,
        edit: @escaping @MainActor @Sendable (_ bottleID: Int, _ change: (inout Bottle) -> Void) -> Void
    ) async {
        let before = bottle.state
        guard level != before else { return }
        var patch = BottlePatch()
        patch.state = .set(level)
        let id = bottle.id
        await toggle(
            lane: "bottle-\(id)", .updateBottle(id: id, patch), affecting: .bottleChange,
            failure: "Couldn\u{2019}t save. Still \(before.label.lowercased()).",
            apply: { edit(id) { $0.state = level } },
            revert: { edit(id) { $0.state = before } },
            onSuccess: { updated in edit(id) { $0 = updated } })
    }

    /// Says `message` under the title for a few seconds.
    public func show(_ message: String, kind: StatusLine.Kind = .info) {
        statusCount += 1
        if kind == .warning { warnings += 1 }
        status = StatusLine(id: statusCount, message: message, kind: kind)
        statusTask?.cancel()
        let shown = statusCount
        statusTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(kind == .failure ? 5 : 3.5))
            guard !Task.isCancelled, let self, statusCount == shown else { return }
            status = nil
        }
    }

    public func dismissStatus() {
        statusTask?.cancel()
        status = nil
    }

    /// Called after a write went through: its stale snapshots go, the screens reload.
    public func didWrite(_ effect: WriteEffect) async {
        await cache?.invalidate(prefixes: effect.prefixes)
        revision += 1
    }

    private func retryingTimeout<Response: Sendable>(
        _ operation: @Sendable (any PolishedAPI) async throws -> Response
    ) async throws -> Response {
        do {
            return try await operation(api)
        } catch APIError.timeout {
            try await Task.sleep(for: retryDelay)
            return try await operation(api)
        }
    }
}

/// A sheet's Save: awaits the server and tells the sheet what to draw. The progress state shows
/// only when the wait passes 300 ms, so a quick answer never flashes a spinner (docs/NATIVE.md 2.3).
@MainActor
@Observable
public final class SaveAction {
    public private(set) var isRunning = false
    public private(set) var showsProgress = false
    public private(set) var error: APIError?

    @ObservationIgnored private let progressDelay: Duration

    public init(progressDelay: Duration = .milliseconds(300)) {
        self.progressDelay = progressDelay
    }

    /// The messages of a 422, by field name ("state", "bought_on", "price_paid_cents", ...).
    public var fieldErrors: [String: String] {
        if case .validation(_, _, let fields)? = error { return fields }
        return [:]
    }

    /// The error's words when it belongs to no field of the form (a 404, a 5xx, offline).
    public var generalError: String? {
        guard let error else { return nil }
        if case .validation(let field, _, _) = error, field != nil { return nil }
        return error.message
    }

    public func clearError() { error = nil }

    /// Runs `work`; nil when it threw (the error is in `error`).
    @discardableResult
    public func run<Result: Sendable>(_ work: @MainActor () async throws -> Result) async -> Result? {
        guard !isRunning else { return nil }
        isRunning = true
        showsProgress = false
        error = nil
        let delay = progressDelay
        let spinner = Task { [weak self] in
            try? await Task.sleep(for: delay)
            guard !Task.isCancelled else { return }
            self?.showsProgress = true
        }
        defer {
            spinner.cancel()
            isRunning = false
            showsProgress = false
        }
        do {
            return try await work()
        } catch let failure as APIError {
            error = failure
        } catch is CancellationError {
        } catch {
            self.error = .offline
        }
        return nil
    }
}
