import Foundation

/// The search's `marks`: Unicode-scalar offsets into the title, as Python counts a `str`, so a
/// title with `™` or a combining accent is indexed through `unicodeScalars` and never through
/// `Character` offsets.
public enum Marks {
    /// The title with each marked span styled by `style`. Spans outside the title are clipped,
    /// empty ones dropped.
    public static func attributed(
        _ title: String, marks: [[Int]], style: (inout AttributedSubstring) -> Void
    ) -> AttributedString {
        var text = AttributedString(title)
        let count = text.unicodeScalars.count
        for pair in marks where pair.count == 2 {
            let start = max(0, min(pair[0], count))
            let end = max(start, min(pair[1], count))
            guard end > start else { continue }
            let lower = text.unicodeScalars.index(text.unicodeScalars.startIndex, offsetBy: start)
            let upper = text.unicodeScalars.index(text.unicodeScalars.startIndex, offsetBy: end)
            style(&text[lower..<upper])
        }
        return text
    }

    /// The marked spans as ranges of `title`.
    public static func ranges(in title: String, marks: [[Int]]) -> [Range<String.Index>] {
        let scalars = title.unicodeScalars
        let count = scalars.count
        return marks.compactMap { pair in
            guard pair.count == 2 else { return nil }
            let start = max(0, min(pair[0], count))
            let end = max(start, min(pair[1], count))
            guard end > start else { return nil }
            let lower = scalars.index(scalars.startIndex, offsetBy: start)
            let upper = scalars.index(scalars.startIndex, offsetBy: end)
            return lower..<upper
        }
    }
}
