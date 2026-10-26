import XCTest

/// Launches the app and keeps screenshots as attachments; `Scripts/test.sh` exports them with
/// `xcresulttool export attachments`. Not a behaviour test yet: the flows arrive from run 2 on.
final class PolishedUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    private func attach(_ name: String, _ app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// The tip gallery, top to bottom: every fixture recipe at four sizes, light and dark.
    @MainActor
    func testGalleryScreenshots() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-screen", "gallery"]
        app.launch()

        let end = app.staticTexts["gallery-end"]
        XCTAssertTrue(app.staticTexts["gallery-light"].waitForExistence(timeout: 20))

        var page = 0
        attach(String(format: "gallery-%02d", page), app)
        while !end.exists || !end.isHittable, page < 40 {
            app.swipeUp(velocity: .slow)
            page += 1
            attach(String(format: "gallery-%02d", page), app)
        }
        XCTAssertTrue(end.exists, "reached the end of the gallery")
    }

    /// Each of the five tabs once.
    @MainActor
    func testTabsScreenshots() throws {
        let app = XCUIApplication()
        app.launch()
        for tab in ["Home", "Shades", "Bottles", "Wheels", "Wishlist"] {
            let button = app.tabBars.buttons[tab].firstMatch
            XCTAssertTrue(button.waitForExistence(timeout: 20), "\(tab) tab")
            button.tap()
            attach("tab-\(tab.lowercased())", app)
        }
    }
}
