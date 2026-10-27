import Foundation

/// The words the web shows for money, dates and tag values (`web.py`: `money`, `day`, `label`,
/// `words`), so the app and the site read the same.
public enum Words {
    /// 1550 -> "$15.50".
    public static func money(_ cents: Int) -> String {
        let sign = cents < 0 ? "-" : ""
        let value = abs(cents)
        return "\(sign)$\(value / 100).\(String(format: "%02d", value % 100))"
    }

    /// "rose-gold" -> "Rose gold".
    public static func label(_ value: String) -> String {
        let text = value.replacingOccurrences(of: "-", with: " ").trimmingCharacters(in: .whitespaces)
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    /// ["glitter", "rose-gold"] -> "Glitter, rose gold".
    public static func list(_ values: [String]) -> String {
        label(values.map { $0.replacingOccurrences(of: "-", with: " ").trimmingCharacters(in: .whitespaces) }.joined(separator: ", "))
    }

    private static let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    /// "2026-10-01" -> "1 Oct 2026"; anything else unchanged.
    public static func day(_ iso: String?) -> String? {
        guard let iso else { return nil }
        let parts = iso.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3, (1...12).contains(parts[1]) else { return iso }
        return "\(parts[2]) \(months[parts[1] - 1]) \(parts[0])"
    }

    /// "2026-10-26" -> a date at noon UTC, for weekday names; nil when it is not a date.
    public static func date(_ iso: String) -> Date? {
        let parts = iso.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: 12))
    }

    /// "Monday 26 October" for an ISO date.
    public static func longDay(_ iso: String) -> String? {
        guard let date = date(iso) else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_GB")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "EEEE d MMMM"
        return formatter.string(from: date)
    }
}

extension ShadeRow {
    /// The line under a shade's name: "Topper, Glitter, holographic" (at most three finishes).
    public var finishLine: String {
        Words.list((isTopper ? ["topper"] : []) + finishes.prefix(3))
    }

    /// "Added by hand" for a manual shade, the status label when it is not plain "In stock".
    public var statusWord: String? {
        guard let status else { return "Added by hand" }
        return status.key == "available" ? nil : status.label
    }
}

extension BottleState {
    /// "Half left", the sentence form used on Home.
    public var leftLabel: String {
        switch self {
        case .full: "Full"
        case .half: "Half left"
        case .low: "Low"
        case .empty: "Empty"
        }
    }
}
