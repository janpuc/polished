import XCTest

/// The base of every flow (docs/NATIVE.md 6.2): each test resets the server's database from its
/// template, launches the app against that server with the development token, and keeps one
/// screenshot per named step. `Scripts/flows.sh` starts the server and passes its address as
/// `TEST_RUNNER_POLISHED_SERVER`.
@MainActor
class FlowCase: XCTestCase {
    private(set) var app = XCUIApplication()
    private var stepNumber = 0

    /// The slug of the wheel the seed makes.
    let wheelSlug = "k3m9xq"
    /// Spirit Fingers: two bottles, one swatch, learned codes.
    let spiritFingersID = 13

    private var server: String {
        ProcessInfo.processInfo.environment["POLISHED_SERVER"] ?? "http://127.0.0.1:8080"
    }

    override func setUp() async throws {
        continueAfterFailure = false
        stepNumber = 0
        try await resetServer()
    }

    private func resetServer() async throws {
        var request = URLRequest(url: URL(string: "\(server)/__test/reset")!)
        request.httpMethod = "POST"
        let (_, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        XCTAssertEqual(status, 200, "POST /__test/reset on \(server): is the server from Scripts/flows.sh running?")
    }

    /// Starts the app signed in with the development token, optionally on a link or signed out.
    @MainActor
    func launch(open url: String? = nil, signedOut: Bool = false, extra: [String] = []) {
        app = XCUIApplication()
        app.launchArguments += ["-server", server, "-uitest", "1"]
        if signedOut { app.launchArguments += ["-signedout", "1"] } else { app.launchArguments += ["-token", "dev"] }
        if let url { app.launchArguments += ["-open", url] }
        app.launchArguments += extra
        app.launch()
    }

    /// The screenshot of a step, kept in the result bundle.
    @MainActor
    func step(_ name: String) {
        stepNumber += 1
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = String(format: "%02d-%@", stepNumber, name)
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Any element by accessibility identifier.
    @MainActor
    func element(_ id: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: id).firstMatch
    }

    @MainActor
    @discardableResult
    func waitFor(_ element: XCUIElement, _ message: String, timeout: TimeInterval = 20) -> XCUIElement {
        if !element.waitForExistence(timeout: timeout) {
            step("FAILED \(message)")
            XCTFail(message)
        }
        return element
    }

    /// Waits until `element` is gone.
    @MainActor
    func waitUntilGone(_ element: XCUIElement, _ message: String, timeout: TimeInterval = 15) {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        if XCTWaiter().wait(for: [expectation], timeout: timeout) != .completed {
            step("FAILED \(message)")
            XCTFail(message)
        }
    }

    /// Any element whose label contains `text`.
    @MainActor
    func labelled(_ text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", text)).firstMatch
    }

    /// Opens a menu and picks one of its items.
    @MainActor
    func choose(_ item: String, from menu: XCUIElement) {
        waitFor(menu, "the menu for \(item)")
        menu.tap()
        let entry = app.buttons[item].firstMatch
        waitFor(entry, "the menu item \(item)", timeout: 8)
        entry.tap()
    }

    /// Scrolls until `element` is clear of the navigation bar and the floating tab bar: an element
    /// can be "hittable" while a bar still covers it, and the tap then lands on the bar. (A form's
    /// lazy rows are not there at all until they scroll in.)
    @MainActor
    func scrollTo(_ element: XCUIElement, _ message: String) {
        let screen = app.windows.firstMatch.frame
        var swipes = 0
        while swipes < 12 {
            if element.exists, element.isHittable {
                let frame = element.frame
                if frame.minY < 150 {
                    app.swipeDown()
                } else if frame.maxY > screen.height - 140 {
                    app.swipeUp()
                } else {
                    break
                }
            } else {
                app.swipeUp()
            }
            swipes += 1
        }
        waitFor(element, message, timeout: 3)
        // A tap on a scroll view that is still decelerating only stops it.
        sleep(1)
    }

    /// A button of the confirmation that just came up (an action sheet on a phone, a popover on
    /// an iPad), not the button of the same name that opened it.
    @MainActor
    func dialogButton(_ title: String) -> XCUIElement {
        let candidates = [app.sheets.buttons[title], app.popovers.buttons[title], app.alerts.buttons[title]]
        let deadline = Date().addingTimeInterval(8)
        while Date() < deadline {
            if let found = candidates.first(where: { $0.exists }) { return found.firstMatch }
            usleep(200_000)
        }
        step("FAILED the confirmation button \(title)")
        XCTFail("the confirmation button \(title)")
        return candidates[0]
    }

    @MainActor
    func tapTab(_ title: String) {
        // A phone's tab bar, or the floating bar at the top of an iPad.
        var button = app.tabBars.buttons[title].firstMatch
        if !button.waitForExistence(timeout: 5) { button = app.buttons[title].firstMatch }
        waitFor(button, "\(title) tab")
        button.tap()
    }

    /// Waits until `element`'s label contains `text`.
    @MainActor
    func waitForLabel(_ element: XCUIElement, containing text: String, timeout: TimeInterval = 15) {
        let predicate = NSPredicate(format: "label CONTAINS %@", text)
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        if XCTWaiter().wait(for: [expectation], timeout: timeout) != .completed {
            step("FAILED label should contain \(text)")
            XCTFail("\(element) label should contain \(text); it is \(element.label)")
        }
    }

    /// Opens the search field (a button on a phone, the field itself on a regular width).
    @MainActor
    func openSearch() {
        let field = app.searchFields.firstMatch
        if !field.waitForExistence(timeout: 3) {
            let button = app.buttons["Search"].firstMatch
            waitFor(button, "the search button")
            button.tap()
        } else {
            field.tap()
        }
        waitFor(app.searchFields.firstMatch, "the search field")
    }

    /// Replaces what is in the search field. Clears with delete keys: the field's own clear button
    /// is not reliably tappable on an iPad, where the field sits in a split view's list column.
    @MainActor
    func type(_ text: String) {
        let field = app.searchFields.firstMatch
        waitFor(field, "the search field")
        if let current = field.value as? String, !current.isEmpty, current != "Search shades" {
            if !field.hasKeyboardFocus { field.tap() }
            field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: current.count))
        }
        field.typeText(text)
        // A fresh simulator introduces slide-to-type with a sheet over the keyboard.
        let introduction = app.buttons["Continue"]
        if introduction.waitForExistence(timeout: 1) { introduction.tap() }
    }
}

extension XCUIElement {
    var hasKeyboardFocus: Bool { (value(forKey: "hasKeyboardFocus") as? Bool) ?? false }
}
