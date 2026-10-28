import PolishedStore
import Testing

@Suite("Builder arrangement")
struct BuilderArrangementTests {
    private let row = 52.0

    @Test("a drag lands on the nearest row and stays inside the stack")
    func target() {
        #expect(BuilderArrangement.target(from: 1, translation: 0, count: 4, rowHeight: row) == 1)
        #expect(BuilderArrangement.target(from: 1, translation: 25, count: 4, rowHeight: row) == 1)
        #expect(BuilderArrangement.target(from: 1, translation: 27, count: 4, rowHeight: row) == 2)
        #expect(BuilderArrangement.target(from: 1, translation: -60, count: 4, rowHeight: row) == 0)
        #expect(BuilderArrangement.target(from: 1, translation: 900, count: 4, rowHeight: row) == 3)
        #expect(BuilderArrangement.target(from: 1, translation: -900, count: 4, rowHeight: row) == 0)
        #expect(BuilderArrangement.target(from: 0, translation: 30, count: 0, rowHeight: row) == 0)
    }

    @Test("the rows the dragged one passes make room")
    func reflow() {
        // Row 0 dragged down to 2: rows 1 and 2 step up.
        let down = (0..<4).map { BuilderArrangement.reflow(index: $0, from: 0, target: 2, rowHeight: row) }
        #expect(down == [0, -row, -row, 0])
        // Row 3 dragged up to 1: rows 1 and 2 step down.
        let up = (0..<4).map { BuilderArrangement.reflow(index: $0, from: 3, target: 1, rowHeight: row) }
        #expect(up == [0, row, row, 0])
        let still = (0..<4).map { BuilderArrangement.reflow(index: $0, from: 2, target: 2, rowHeight: row) }
        #expect(still == [0, 0, 0, 0])
    }

    @Test("a drop is as many single moves as rows crossed")
    func moves() {
        #expect(BuilderArrangement.moves(from: 0, target: 2) == [false, false])
        #expect(BuilderArrangement.moves(from: 3, target: 1) == [true, true])
        #expect(BuilderArrangement.moves(from: 2, target: 2).isEmpty)
    }
}
