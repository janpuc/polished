import XCTest

/// The tip gallery, screenshotted top to bottom: `Scripts/gallery.sh` exports the attachments.
/// Needs no server.
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
}
