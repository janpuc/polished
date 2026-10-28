import Foundation

/// The mapping from how the phone is held to where the light is (docs/NATIVE.md 4.4): the tilt
/// from the held position, clamped to ±20°, becomes `lx` and `ly` around the v3 static light.
/// Pure, so the vectors are tested apart from Core Motion.
public enum TipLightMapper {
    public static let clampDegrees = 20.0
    /// The weight of a new sample in the low-pass filter.
    public static let smoothing = 0.18
    /// How fast the held position follows the phone: after this many seconds a changed grip has
    /// recentred to 63%.
    public static let driftSeconds = 4.0

    /// The light for a tilt of `rollDegrees` (left/right) and `pitchDegrees` (top away/towards).
    public static func light(rollDegrees: Double, pitchDegrees: Double) -> TipLight {
        let roll = clamp(rollDegrees) / clampDegrees
        let pitch = clamp(pitchDegrees) / clampDegrees
        return TipLight(lx: TipLight.static.lx + roll * 0.6, ly: TipLight.static.ly + pitch * 0.4)
    }

    public static func clamp(_ degrees: Double) -> Double {
        min(max(degrees, -clampDegrees), clampDegrees)
    }

    /// One step of the low-pass filter.
    public static func smoothed(previous: Double, sample: Double, alpha: Double = smoothing) -> Double {
        previous + (sample - previous) * alpha
    }

    /// The reference after `dt` seconds of drifting towards the current angle.
    public static func drifted(reference: Double, current: Double, dt: Double, seconds: Double = driftSeconds) -> Double {
        reference + (current - reference) * (1 - exp(-max(dt, 0) / seconds))
    }
}

/// The tilt of the phone as the filter sees it, fed one motion sample at a time: angles are
/// relative to the attitude captured when the filter started (or `recentre()`), the reference
/// drifts towards where the phone is, and the result is low-pass filtered.
public struct TipLightFilter: Sendable, Equatable {
    private var referenceRoll = 0.0
    private var referencePitch = 0.0
    private var smoothedRoll = 0.0
    private var smoothedPitch = 0.0

    public init() {}

    /// The held position is where the phone is now.
    public mutating func recentre() {
        self = TipLightFilter()
    }

    /// `rollDegrees` and `pitchDegrees` are relative to the attitude captured at the start.
    public mutating func update(rollDegrees: Double, pitchDegrees: Double, dt: Double) -> TipLight {
        referenceRoll = TipLightMapper.drifted(reference: referenceRoll, current: rollDegrees, dt: dt)
        referencePitch = TipLightMapper.drifted(reference: referencePitch, current: pitchDegrees, dt: dt)
        smoothedRoll = TipLightMapper.smoothed(previous: smoothedRoll, sample: rollDegrees - referenceRoll)
        smoothedPitch = TipLightMapper.smoothed(previous: smoothedPitch, sample: pitchDegrees - referencePitch)
        return TipLightMapper.light(rollDegrees: smoothedRoll, pitchDegrees: smoothedPitch)
    }
}

/// Whether the light may move (docs/NATIVE.md 4.4). Every reason to hold still is a field; the
/// light is live only when none applies.
public struct LightGate: Sendable, Equatable {
    public var reduceMotion = false
    public var lowPowerMode = false
    public var thermalSerious = false
    public var sceneActive = true
    public var motionAvailable = true
    public var simulator = false

    public init(
        reduceMotion: Bool = false, lowPowerMode: Bool = false, thermalSerious: Bool = false,
        sceneActive: Bool = true, motionAvailable: Bool = true, simulator: Bool = false
    ) {
        self.reduceMotion = reduceMotion
        self.lowPowerMode = lowPowerMode
        self.thermalSerious = thermalSerious
        self.sceneActive = sceneActive
        self.motionAvailable = motionAvailable
        self.simulator = simulator
    }

    public var isLive: Bool {
        !reduceMotion && !lowPowerMode && !thermalSerious && sceneActive && motionAvailable && !simulator
    }
}

/// How strongly the shader lights a recipe (docs/advice/fable-builder-v2-tilt-2026-10-28.md B):
/// the specular pool, the holo band and the gloss that multiplies the band, from the layers
/// that show, the last opaque one upward.
public struct TipLightStrengths: Sendable, Equatable {
    public var specular: Double
    public var holo: Double
    public var gloss: Double

    public init(specular: Double, holo: Double, gloss: Double) {
        self.specular = specular
        self.holo = holo
        self.gloss = gloss
    }

    static let metallic: Set<String> = ["metallic", "chrome", "reflective"]
    static let maxHolo = 0.3

    public init(_ recipe: TipRecipe) {
        var visible = recipe.layers
        if let last = visible.lastIndex(where: \.opaque) { visible = Array(visible[last...]) }

        var holo = 0.0
        for layer in visible {
            var part = 0.0
            if layer.finishes.contains("holographic") { part += 0.22 }
            if layer.finishes.contains("iridescent") { part += 0.14 }
            if layer.finishes.contains("flakie") { part += 0.10 }
            holo += layer.topper ? part * 0.6 : part
        }

        guard let top = visible.last(where: { !$0.clear }) else {
            self.init(specular: 0, holo: 0, gloss: 0)
            return
        }
        // The gloss follows the painter: it is off when the last layer is matte.
        let glossy = !(recipe.layers.last?.finishes.contains("matte") ?? false)
        let specular: Double
        if top.finishes.contains("matte") {
            specular = 0
        } else if !top.finishes.isDisjoint(with: Self.metallic) {
            specular = 0.6
        } else if top.finishes.contains("glitter") {
            specular = 0.45
        } else {
            specular = 0.35
        }
        self.init(specular: specular, holo: min(holo, Self.maxHolo), gloss: glossy ? 1 : 0)
    }
}
