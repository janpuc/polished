import Foundation
import NailTips
import Testing

/// One case of spec/tips/cases.json: the layers, and the ops tips.py painted for them.
struct TipCase: Decodable, Sendable, CustomTestStringConvertible {
    var name: String
    var layers: [TipShade]
    var ops: [TipOp]

    var testDescription: String { name }
}

private struct TipCases: Decodable {
    var cases: [TipCase]
}

enum TipFixtures {
    static let cases: [TipCase] = {
        // Fails the whole suite loudly when the fixture is missing, instead of passing on zero cases.
        do { return try Fixtures.decode(TipCases.self, from: "tips/cases.json").cases } catch {
            fatalError("spec/tips/cases.json: \(error)")
        }
    }()
}

/// Whether two JSON trees are equal: strings and keys exactly, numbers within a tolerance.
func jsonClose(_ a: Any, _ b: Any, tolerance: Double = 0.001) -> Bool {
    switch (a, b) {
    case let (a as [String: Any], b as [String: Any]):
        return a.keys == b.keys && a.allSatisfy { key, value in jsonClose(value, b[key]!, tolerance: tolerance) }
    case let (a as [Any], b as [Any]):
        return a.count == b.count && zip(a, b).allSatisfy { jsonClose($0, $1, tolerance: tolerance) }
    case let (a as String, b as String):
        return a == b
    case let (a as NSNumber, b as NSNumber):
        return abs(a.doubleValue - b.doubleValue) <= tolerance
    case (is NSNull, is NSNull):
        return true
    default:
        return false
    }
}

@Suite("Tip renderer parity")
struct TipParityTests {
    @Test func fixtureHasEveryCase() {
        #expect(TipFixtures.cases.count == 46)
    }

    @Test(arguments: TipFixtures.cases)
    func opsMatchTipsPy(_ tipCase: TipCase) throws {
        let ops = TipPainter.ops(for: tipCase.layers)
        #expect(ops.count == tipCase.ops.count, "op count")
        #expect(ops.map(\.kind) == tipCase.ops.map(\.kind), "op kinds in order")

        let encoder = JSONEncoder()
        for (index, (ours, recorded)) in zip(ops, tipCase.ops).enumerated() {
            let a = try JSONSerialization.jsonObject(with: encoder.encode(ours))
            let b = try JSONSerialization.jsonObject(with: encoder.encode(recorded))
            #expect(jsonClose(a, b), "op \(index) (\(ours.kind)) differs: \(a) vs \(b)")
        }
    }

    /// The decoded recording must itself be the raw JSON, so a field the decoder drops fails here.
    @Test(arguments: TipFixtures.cases)
    func recordedOpsRoundTrip(_ tipCase: TipCase) throws {
        let raw = try Fixtures.json("tips/cases.json") as? [String: Any]
        let cases = try #require(raw?["cases"] as? [[String: Any]])
        let recorded = try #require(cases.first { $0["name"] as? String == tipCase.name }?["ops"])
        let encoded = try JSONSerialization.jsonObject(with: JSONEncoder().encode(tipCase.ops))
        #expect(jsonClose(encoded, recorded))
    }
}

@Suite("TipRandom")
struct TipRandomTests {
    private struct Vector: Decodable {
        var seed: UInt64
        var random: [Double]
        var below1000: [Int]

        private enum CodingKeys: String, CodingKey {
            case seed, random
            case below1000 = "below_1000"
        }
    }

    private struct Vectors: Decodable {
        var vectors: [Vector]
    }

    private static let vectors: [Vector] = {
        do { return try Fixtures.decode(Vectors.self, from: "tips/random.json").vectors } catch {
            fatalError("spec/tips/random.json: \(error)")
        }
    }()

    @Test func seedZeroFirstWord() {
        var rng = TipRandom(seed: 0)
        #expect(rng.next() == 0xE220_A839_7B1D_CDAF)
    }

    @Test(arguments: vectors.map(\.seed))
    func matchesRandomJSON(seed: UInt64) throws {
        let vector = try #require(Self.vectors.first { $0.seed == seed })
        var rng = TipRandom(seed: seed)
        for expected in vector.random {
            #expect(rng.random() == expected)  // bit-exact, not within a tolerance
        }
        for expected in vector.below1000 {
            #expect(rng.below(1000) == expected)
        }
    }
}
