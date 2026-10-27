import Foundation

/// How a person's typing becomes the contract's values: money as cents, dates as `YYYY-MM-DD`.
public enum Entry {
    /// "15.50", "15,5", "$15" or "15" as cents (1550, 1550, 1500, 1500); nil when the text is not an
    /// amount the server accepts (0 to 9999.99, at most two decimals). Empty text is not an amount.
    public static func cents(_ text: String) -> Int? {
        var digits = text.trimmingCharacters(in: .whitespaces)
        if digits.hasPrefix("$") { digits.removeFirst() }
        digits = digits.replacingOccurrences(of: ",", with: ".")
        guard !digits.isEmpty, digits != "." else { return nil }
        let parts = digits.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count <= 2, parts.allSatisfy({ $0.allSatisfy(\.isASCIIDigit) }) else { return nil }
        let whole = parts[0]
        let fraction = parts.count == 2 ? parts[1] : ""
        guard fraction.count <= 2, !(whole.isEmpty && fraction.isEmpty), whole.count <= 4 else { return nil }
        let cents = (Int(whole) ?? 0) * 100 + (Int(fraction.padding(toLength: 2, withPad: "0", startingAt: 0)) ?? 0)
        return cents <= 999_999 ? cents : nil
    }

    /// 1550 -> "15.50", the text a price field starts with.
    public static func field(cents: Int) -> String {
        "\(cents / 100).\(String(format: "%02d", cents % 100))"
    }
}

extension Character {
    fileprivate var isASCIIDigit: Bool { ("0"..."9").contains(self) }
}

/// Days as the household keeps them: `YYYY-MM-DD` in the server's time zone (`/me` →
/// `server.timezone`), which also decides what "today" is and so what is "in the future".
public struct HouseholdDay: Sendable {
    public var timeZone: TimeZone

    public init(timeZone: TimeZone = .current) {
        self.timeZone = timeZone
    }

    private var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        return calendar
    }

    /// The moment at noon of `iso` in the household's zone; nil when it is not a date.
    public func date(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let parts = iso.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: 12))
    }

    public func iso(_ date: Date) -> String {
        let parts = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// Today in the household's zone, as of `now`.
    public func today(now: Date = Date()) -> String { iso(now) }

    /// The day before today.
    public func yesterday(now: Date = Date()) -> String {
        iso(calendar.date(byAdding: .day, value: -1, to: now) ?? now)
    }

    /// Whether `iso` is after today: the server refuses those.
    public func isFuture(_ iso: String, now: Date = Date()) -> Bool {
        iso > today(now: now)
    }
}
