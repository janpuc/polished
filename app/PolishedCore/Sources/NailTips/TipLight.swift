/// Where the light falls on a tip, in -1...1 on each axis from the tip's centre. `static` is
/// the v3 light, top left; run 6 adds a live one driven by Core Motion.
public struct TipLight: Sendable, Equatable {
    public var lx: Double
    public var ly: Double

    public init(lx: Double, ly: Double) {
        self.lx = lx
        self.ly = ly
    }

    public static let `static` = TipLight(lx: -0.35, ly: -0.55)
}
