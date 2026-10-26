/// What a tip shows: the layers of a stack (a single shade is a stack of one). Hashable, so it
/// keys the image cache.
public struct TipRecipe: Sendable, Hashable {
    public var layers: [TipShade]

    public init(_ layers: [TipShade]) {
        self.layers = layers
    }

    public init(_ shade: TipShade) {
        layers = [shade]
    }

    /// The paint plan, worked out on each call.
    public var ops: [TipOp] {
        TipPainter.ops(for: layers)
    }
}
