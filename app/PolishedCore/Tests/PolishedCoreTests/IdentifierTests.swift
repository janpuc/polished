import Foundation
import PolishedModels
import Testing

private struct Vector: Decodable, Sendable, CustomTestStringConvertible {
    var input: String
    var output: String?

    var testDescription: String { "\(input.debugDescription) -> \(output ?? "nil")" }
}

private struct Vectors: Decodable {
    var vectors: [Vector]
}

private func load(_ path: String) -> [Vector] {
    do { return try Fixtures.decode(Vectors.self, from: path).vectors } catch {
        fatalError("spec/\(path): \(error)")
    }
}

@Suite("Identifier normalisation")
struct IdentifierTests {
    @Test(arguments: load("identifiers/gtin.json"))
    fileprivate func gtin(_ vector: Vector) {
        #expect(Identifiers.normaliseGTIN(vector.input) == vector.output)
    }
}
