import Foundation
import PolishedModels
import Testing

@Suite("Marks")
struct MarksTests {
    /// The spans the style closure was handed, as plain strings.
    private func marked(_ title: String, _ marks: [[Int]]) -> [String] {
        let text = Marks.attributed(title, marks: marks) { $0.inlinePresentationIntent = .stronglyEmphasized }
        return text.runs.compactMap { run in
            run.inlinePresentationIntent == .stronglyEmphasized ? String(text[run.range].characters) : nil
        }
    }

    @Test func plainTitle() {
        #expect(marked("Magnetic Taco", [[0, 8], [9, 13]]) == ["Magnetic", "Taco"])
    }

    @Test("offsets count Unicode scalars, as Python's str does")
    func scalarsNotCharacters() {
        // "Crème Brûlée" in decomposed form: "e" + U+0300 are two scalars, one Character.
        let title = "Cre\u{0300}me Bru\u{0302}le\u{0301}e"
        #expect(title.unicodeScalars.count == 15)
        #expect(marked(title, [[7, 15]]) == ["Bru\u{0302}le\u{0301}e"])
    }

    @Test func trademarkSign() {
        // "Aurora Unicorn Skin™": the sign is one scalar; a mark at its end.
        #expect(marked("Aurora Unicorn Skin\u{2122}", [[15, 20]]) == ["Skin\u{2122}"])
    }

    @Test func clipsOutOfRangeAndDropsEmptySpans() {
        #expect(marked("Spirit Fingers", [[7, 40], [3, 3], [9, 2]]) == ["Fingers"])
        #expect(marked("Spirit", [[-4, 3]]) == ["Spi"])
    }

    @Test func rangesAreStringIndices() {
        let title = "Holo Magnetic Taco"
        let ranges = Marks.ranges(in: title, marks: [[5, 13]])
        #expect(ranges.map { String(title[$0]) } == ["Magnetic"])
    }
}

@Suite("Words")
struct WordsTests {
    @Test func money() {
        #expect(Words.money(1550) == "$15.50")
        #expect(Words.money(5) == "$0.05")
        #expect(Words.money(8750) == "$87.50")
    }

    @Test func labels() {
        #expect(Words.label("rose-gold") == "Rose gold")
        #expect(Words.list(["glitter", "rose-gold"]) == "Glitter, rose gold")
        #expect(Words.day("2026-10-01") == "1 Oct 2026")
        #expect(Words.day("soon") == "soon")
        #expect(Words.longDay("2026-10-26") == "Monday 26 October")
    }
}
