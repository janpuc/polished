import Foundation
import PolishedModels
import Testing

@Suite("Entry")
struct EntryTests {
    @Test(arguments: [
        ("15.50", 1550), ("15,5", 1550), ("$15", 1500), ("15", 1500), (" 0.99 ", 99), (".5", 50), ("9999.99", 999_999), ("0", 0),
    ])
    func centsFromText(text: String, expected: Int) {
        #expect(Entry.cents(text) == expected)
    }

    @Test(arguments: ["", " ", ".", "abc", "1.234", "1.2.3", "-5", "10000", "15 dollars", "$"])
    func notAnAmount(text: String) {
        #expect(Entry.cents(text) == nil)
    }

    @Test func fieldText() {
        #expect(Entry.field(cents: 1550) == "15.50")
        #expect(Entry.field(cents: 5) == "0.05")
        #expect(Entry.cents(Entry.field(cents: 1234)) == 1234)
    }
}

@Suite("HouseholdDay")
struct HouseholdDayTests {
    /// 2026-10-27 01:30 UTC is still the 26th in Los Angeles and already the 27th in Warsaw.
    private let moment = Date(timeIntervalSince1970: 1_793_064_600)

    @Test func todayFollowsTheHouseholdsZone() {
        #expect(HouseholdDay(timeZone: TimeZone(identifier: "America/Los_Angeles")!).today(now: moment) == "2026-10-26")
        #expect(HouseholdDay(timeZone: TimeZone(identifier: "Europe/Warsaw")!).today(now: moment) == "2026-10-27")
    }

    @Test func yesterdayAndTheFuture() {
        let warsaw = HouseholdDay(timeZone: TimeZone(identifier: "Europe/Warsaw")!)
        #expect(warsaw.yesterday(now: moment) == "2026-10-26")
        #expect(warsaw.isFuture("2026-10-28", now: moment))
        #expect(!warsaw.isFuture("2026-10-27", now: moment))
    }

    @Test func datesRoundTrip() throws {
        let warsaw = HouseholdDay(timeZone: TimeZone(identifier: "Europe/Warsaw")!)
        let date = try #require(warsaw.date("2026-07-21"))
        #expect(warsaw.iso(date) == "2026-07-21")
        #expect(warsaw.date("not a date") == nil)
    }
}

@Suite("Words.wait")
struct WaitTests {
    @Test func roundsUpToMinutes() {
        #expect(Words.wait(seconds: 45) == "1 min")
        #expect(Words.wait(seconds: 3660) == "61 min")
        #expect(Words.wait(seconds: 3600) == "1 h")
        #expect(Words.wait(seconds: 7200) == "2 h")
        #expect(Words.wait(seconds: 0) == "1 min")
    }
}
