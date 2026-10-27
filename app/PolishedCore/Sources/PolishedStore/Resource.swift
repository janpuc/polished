import Observation
import PolishedAPI
import PolishedModels
import Foundation

/// One screen's data: the snapshot first (instant, and offline), then the server's answer
/// (docs/NATIVE.md 2.3). `value` only ever moves forward; a failed refresh keeps it and sets
/// `error`, so the screen shows what was here with a status line rather than a blocking page.
@MainActor
@Observable
public final class Resource<Value: Decodable & Sendable> {
    public private(set) var value: Value?
    /// The answer on screen is the snapshot, the server has not confirmed it yet.
    public private(set) var isStale = false
    public private(set) var isLoading = false
    public private(set) var error: APIError?
    @ObservationIgnored private var loadedKey: String?
    /// A list whose endpoint changes as the person types keeps the last results on screen until
    /// the new ones arrive, instead of blinking empty between keys.
    @ObservationIgnored private let keepsValueAcrossEndpoints: Bool

    public init(_ value: Value? = nil, keepsValueAcrossEndpoints: Bool = false) {
        self.value = value
        self.keepsValueAcrossEndpoints = keepsValueAcrossEndpoints
    }

    public var isOffline: Bool { error == .offline && value != nil }

    /// Reads the snapshot (when nothing is on screen for this endpoint yet), then asks the server.
    public func load(_ endpoint: Endpoint<Value>, api: any PolishedAPI) async {
        let changed = loadedKey != endpoint.key
        if changed {
            loadedKey = endpoint.key
            if !keepsValueAcrossEndpoints { value = nil }
            error = nil
        }
        if changed || value == nil, let snapshot = await api.cached(endpoint) {
            value = snapshot
            isStale = true
        }
        isLoading = true
        defer { isLoading = false }
        do {
            let fresh = try await api.get(endpoint)
            value = fresh
            isStale = false
            error = nil
        } catch is CancellationError {
            return
        } catch let failure as APIError {
            error = failure
        } catch {
            self.error = .offline
        }
    }

    /// Changes the value in place: an optimistic toggle, before the server has answered.
    public func update(_ change: (inout Value) -> Void) {
        guard var current = value else { return }
        change(&current)
        value = current
    }

    /// Forgets the value (a choice that has been overtaken by the server's own).
    public func clear() {
        value = nil
    }

    /// The server's answer is the new value without a snapshot detour (a second page, "Another").
    public func set(_ newValue: Value) {
        value = newValue
        isStale = false
        error = nil
    }
}
