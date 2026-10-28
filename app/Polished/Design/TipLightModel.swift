import CoreMotion
import NailTips
import Observation
import SwiftUI
import UIKit

/// Where the light is, as the phone is tilted (docs/NATIVE.md 4.4). One per app, in the
/// environment. It reads Core Motion only while a `live` tip is on screen and the `LightGate` is
/// open; otherwise `light` is the static light and `isShaded` is false, so every tip looks as it
/// does in a list.
@MainActor @Observable
final class TipLightModel {
    /// The light every live tip is lit by.
    private(set) var light = TipLight.static
    /// The shader draws the pool and the holo band instead of the canvas: the light is live, or
    /// pinned for a screenshot.
    private(set) var isShaded = false

    @ObservationIgnored private var gate = LightGate()
    @ObservationIgnored private var pinned: TipLight?
    @ObservationIgnored private var liveViews = 0
    @ObservationIgnored private var running = false
    @ObservationIgnored private let motion = CMMotionManager()
    @ObservationIgnored private var reference: CMAttitude?
    @ObservationIgnored private var filter = TipLightFilter()
    @ObservationIgnored private var lastTimestamp: TimeInterval?
    @ObservationIgnored private var observers: [any NSObjectProtocol] = []

    init() {
        gate.motionAvailable = motion.isDeviceMotionAvailable
        #if targetEnvironment(simulator)
        gate.simulator = true
        #endif
        refreshSystemGate()
        let center = NotificationCenter.default
        let names: [Notification.Name] = [
            UIAccessibility.reduceMotionStatusDidChangeNotification,
            .NSProcessInfoPowerStateDidChange,
            ProcessInfo.thermalStateDidChangeNotification,
        ]
        observers = names.map { name in
            center.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated { self?.refreshSystemGate() }
            }
        }
    }

    // MARK: Inputs

    /// A screenshot's light (`-light lx,ly`): the shader draws it and nothing moves.
    func pin(_ light: TipLight) {
        pinned = light
        update()
    }

    func setScenePhase(_ phase: ScenePhase) {
        let active = phase == .active
        guard gate.sceneActive != active else { return }
        gate.sceneActive = active
        update()
    }

    /// A live tip appeared or went away; motion runs while at least one is on screen.
    func viewAppeared() {
        liveViews += 1
        update()
    }

    func viewDisappeared() {
        liveViews = max(liveViews - 1, 0)
        update()
    }

    // MARK: Gate

    private func refreshSystemGate() {
        gate.reduceMotion = UIAccessibility.isReduceMotionEnabled
        gate.lowPowerMode = ProcessInfo.processInfo.isLowPowerModeEnabled
        gate.thermalSerious = ProcessInfo.processInfo.thermalState.rawValue >= ProcessInfo.ThermalState.serious.rawValue
        update()
    }

    private func update() {
        if let pinned {
            stop()
            light = pinned
            isShaded = true
            return
        }
        if gate.isLive, liveViews > 0 {
            start()
            isShaded = true
        } else {
            stop()
            light = .static
            isShaded = false
        }
    }

    // MARK: Core Motion

    private func start() {
        guard !running else { return }
        running = true
        // The held position is wherever the phone is now (and again when the app comes back).
        reference = nil
        lastTimestamp = nil
        filter.recentre()
        motion.deviceMotionUpdateInterval = 1.0 / 30
        motion.startDeviceMotionUpdates(using: .xArbitraryZVertical, to: .main) { [weak self] data, _ in
            guard let data else { return }
            MainActor.assumeIsolated { self?.handle(data) }
        }
    }

    private func stop() {
        guard running else { return }
        running = false
        motion.stopDeviceMotionUpdates()
        reference = nil
    }

    private func handle(_ data: CMDeviceMotion) {
        guard running, pinned == nil else { return }
        guard let held = reference else {
            reference = data.attitude.copy() as? CMAttitude
            lastTimestamp = data.timestamp
            return
        }
        // `multiply(byInverseOf:)` changes the attitude it is called on, and that one is reused.
        guard let relative = data.attitude.copy() as? CMAttitude else { return }
        relative.multiply(byInverseOf: held)
        let dt = lastTimestamp.map { data.timestamp - $0 } ?? 1.0 / 30
        lastTimestamp = data.timestamp
        let next = filter.update(
            rollDegrees: relative.roll * 180 / .pi, pitchDegrees: relative.pitch * 180 / .pi, dt: dt)
        if next != light { light = next }
    }
}
