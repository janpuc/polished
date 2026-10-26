/// Barcode and printed-code normalisation: ports of `gtin.py` and `normalise_printed` in
/// `identifiers.py`, checked by `spec/identifiers/*.json`.
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

    /// Python's `\d` and `str.isdigit` for the printed code: any decimal digit (category Nd).
    private static func isDecimalDigit(_ scalar: Unicode.Scalar) -> Bool {
        scalar.properties.generalCategory == .decimalNumber
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

    /// Strip, uppercase, remove spaces; all digits gets the prefix `P`; the result must be one
    /// or two letters A-Z and one to five digits. "259" and "p 259" are "P259"; "hello" is nil.
    public static func normalisePrinted(_ raw: String) -> String? {
        var text = withoutWhitespace(raw).uppercased()
        if !text.isEmpty, text.unicodeScalars.allSatisfy(isDecimalDigit) { text = "P" + text }
        let scalars = Array(text.unicodeScalars)
        let letters = scalars.prefix { $0.value >= 0x41 && $0.value <= 0x5A }.count
        let digits = scalars.count - letters
        guard (1...2).contains(letters), (1...5).contains(digits),
            scalars.dropFirst(letters).allSatisfy(isDecimalDigit)
        else { return nil }
        return text
    }
}
