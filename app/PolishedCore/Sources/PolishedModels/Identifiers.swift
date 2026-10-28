/// Barcode normalisation: a port of `gtin.py`, checked by `spec/identifiers/gtin.json`.
public enum Identifiers {
    private static let gtinLengths: Set<Int> = [8, 12, 13, 14]
    private static let canonicalLength = 13

    /// ASCII digits only, once whitespace is gone (Python's `str.split()` whitespace).
    private static func withoutWhitespace(_ raw: String) -> String {
        String(raw.unicodeScalars.filter { !$0.properties.isWhitespace })
    }

    private static func isAsciiDigits(_ text: String) -> Bool {
        !text.isEmpty && text.unicodeScalars.allSatisfy { $0.value >= 0x30 && $0.value <= 0x39 }
    }

    /// GS1 check digit: from the right, the digit before the check is weighted 3, then 1, 3, …
    /// and the weighted sum, check digit included, is a multiple of ten.
    static func checkDigitOK(_ digits: [Int]) -> Bool {
        guard let check = digits.last else { return false }
        let total = digits.dropLast().reversed().enumerated().reduce(0) { sum, item in
            sum + item.element * (item.offset % 2 == 0 ? 3 : 1)
        }
        return (total + check) % 10 == 0
    }

    /// Whitespace removed; digits only; 8, 12, 13 or 14 of them with a valid check digit; a
    /// 14-digit value only with a leading 0 (otherwise it is a case or ITF-14 code, not a
    /// bottle). Returns the 13-digit form.
    public static func normaliseGTIN(_ raw: String) -> String? {
        var digits = withoutWhitespace(raw)
        guard isAsciiDigits(digits), gtinLengths.contains(digits.count) else { return nil }
        if digits.count == 14 {
            guard digits.hasPrefix("0") else { return nil }
            digits.removeFirst()
        }
        guard checkDigitOK(digits.compactMap(\.wholeNumberValue)) else { return nil }
        return String(repeating: "0", count: canonicalLength - digits.count) + digits
    }
}
