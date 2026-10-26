/// SplitMix64 seeded with the shade id: the same numbers as `TipRandom` in `tips.py`
/// (`spec/tips/random.json` holds the vectors).
public struct TipRandom: Sendable {
    private var state: UInt64

    public init(seed: UInt64) {
        state = seed
    }

    public mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    public mutating func random() -> Double {
        Double(next() >> 11) * 0x1.0p-53
    }

    public mutating func uniform(_ a: Double, _ b: Double) -> Double {
        a + (b - a) * random()
    }

    public mutating func below(_ n: Int) -> Int {
        Int(random() * Double(n))
    }

    public mutating func choice<T>(_ items: [T]) -> T {
        items[below(items.count)]
    }

    public mutating func randint(_ a: Int, _ b: Int) -> Int {
        a + below(b - a + 1)
    }

    public mutating func randrange(_ n: Int) -> Int {
        below(n)
    }
}
