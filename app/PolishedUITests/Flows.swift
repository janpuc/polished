import XCTest

// One XCTestCase per flow, the names of the web's flows where there is one (tests/e2e/flows).

/// Shades: the list, the search with matches washed in, fuzzy words, accents, no match.
final class SearchFlow: FlowCase {
    @MainActor
    func testSearch() throws {
        launch()
        tapTab("Shades")
        waitForLabel(element("result-count"), containing: "23 shades")
        step("shades-list")

        openSearch()
        type("Spirit Fingers")
        waitFor(element("shade-row-\(spiritFingersID)"), "exact title")
        step("exact-title-first")

        type("magentic taco")
        waitForLabel(element("result-count"), containing: "closest first")
        step("fuzzy-with-marks")

        type("onecoat")
        waitFor(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'One-Coat Black'")).firstMatch, "onecoat finds One-Coat Black")
        step("onecoat")

        type("creme brulee")
        waitFor(app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'Crème Brûlée'")).firstMatch, "accents are folded")
        step("accents")

        type("overstim")
        waitFor(element("no-results"), "nothing matches")
        step("no-results")
    }
}

/// Every tab once, and Settings.
final class TabsFlow: FlowCase {
    @MainActor
    func testTabs() throws {
        launch()
        waitFor(app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Good'")).firstMatch, "the greeting")
        waitFor(element("another-button"), "Wear today")
        step("home")
        for tab in ["Shades", "Bottles", "Wheels", "Wishlist"] {
            tapTab(tab)
            sleep(2)
            step(tab.lowercased())
        }
        tapTab("Home")
        let settings = element("settings-button")
        waitFor(settings, "the Settings button")
        settings.tap()
        // The top of the list: on an iPad Settings is a form-sized sheet and the version row sits below its fold.
        waitFor(app.staticTexts["Signed in as"].firstMatch, "Settings")
        sleep(1)
        step("settings")
    }
}

/// Bottles by level, and History by month.
final class HistoryFlow: FlowCase {
    @MainActor
    func testHistory() throws {
        launch()
        tapTab("Bottles")
        waitFor(element("bottle-count"), "the bottle list")
        waitForLabel(element("bottle-count"), containing: "bottles in")
        step("collection")

        let half = app.buttons["Half"].firstMatch
        waitFor(half, "the Half chip")
        half.tap()
        sleep(1)
        step("level-half")

        let mode = app.segmentedControls["bottles-mode"].firstMatch
        waitFor(mode, "the Collection and History control")
        mode.buttons["History"].tap()
        waitFor(app.staticTexts["October 2026"].firstMatch, "the October 2026 month")
        step("history")
    }
}

/// Links into the app: a wheel, a shade, one that is not ours.
final class DeepLinkFlow: FlowCase {
    @MainActor
    func testDeepLink() throws {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)")
        waitFor(element("wheel-ring"), "the wheel opened by its link")
        waitFor(app.staticTexts["Holos"].firstMatch, "the wheel's name")
        sleep(1)
        step("wheel-link")
        app.terminate()

        launch(open: "https://polished.janpuc.com/shades/\(spiritFingersID)")
        waitFor(app.staticTexts["Spirit Fingers"].firstMatch, "the shade opened by its link")
        sleep(2)
        step("shade-link")
        app.terminate()

        launch(open: "https://polished.janpuc.com/w/NOPE")
        waitFor(element("another-button"), "a link that is not ours leaves Home alone")
        step("rejected-link")
    }
}

/// The shade page from the list: the zoom, the plate, the photos, the bottles, the facts.
final class ShadeDetailFlow: FlowCase {
    @MainActor
    func testShadeDetail() throws {
        launch()
        tapTab("Shades")
        waitForLabel(element("result-count"), containing: "23 shades")
        openSearch()
        type("spirit")
        let row = element("shade-row-\(spiritFingersID)")
        waitFor(row, "Spirit Fingers in the results")
        row.tap()
        waitFor(app.staticTexts["Spirit Fingers"].firstMatch, "the shade page")
        sleep(3)
        step("top")
        app.swipeUp()
        sleep(1)
        step("bottles-and-facts")
        app.swipeUp()
        sleep(1)
        step("swatched-on")
    }
}

/// The wheel: its ring of real tips, a swatch opened from a slot.
final class WheelFlow: FlowCase {
    @MainActor
    func testWheel() throws {
        launch()
        tapTab("Wheels")
        let card = element("wheel-card-\(wheelSlug)")
        waitFor(card, "the wheel list")
        step("wheels")
        card.tap()
        waitFor(element("wheel-ring"), "the ring")
        sleep(1)
        step("ring")
        let slot = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Slot 12'")).firstMatch
        waitFor(slot, "slot 12")
        slot.tap()
        waitFor(app.staticTexts["Slot 12"].firstMatch, "the swatch sheet")
        sleep(1)
        step("swatch")
    }
}

/// The wishlist head and rows.
final class WishlistFlow: FlowCase {
    @MainActor
    func testWishlist() throws {
        launch()
        tapTab("Wishlist")
        waitFor(element("checkout-button"), "the checkout button")
        step("wishlist")
        let everything = app.segmentedControls["wishlist-include"].buttons["Want most"]
        if everything.exists {
            everything.tap()
            sleep(1)
            step("want-most")
        }
    }
}

/// The signed-out screen (the sign-in itself needs a real Pocket ID and a device).
final class SignInFlow: FlowCase {
    @MainActor
    func testSignIn() throws {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)", signedOut: true)
        waitFor(element("sign-in-button"), "the sign-in button")
        step("sign-in")
    }
}

// MARK: Writes (run 3)

/// Add a bottle from a shade's page: level, a date preset, a price, then the arrival.
final class AddBottleFlow: FlowCase {
    @MainActor
    func testAddBottle() throws {
        launch()
        tapTab("Shades")
        waitForLabel(element("result-count"), containing: "23 shades")
        openSearch()
        type("hit the")
        let row = element("shade-row-3")
        waitFor(row, "Hit The Lights in the results")
        row.tap()
        let add = waitFor(element("add-bottle"), "the Add bottle button")
        sleep(2)
        step("shade")
        add.tap()

        waitFor(app.navigationBars["Add bottle"], "the Add bottle sheet")
        step("sheet")
        let half = waitFor(element("level-half"), "the Half segment")
        half.tap()
        let yesterday = waitFor(app.buttons["Yesterday"].firstMatch, "the Yesterday preset")
        yesterday.tap()
        let more = waitFor(app.buttons["More details"].firstMatch, "More details")
        more.tap()
        let price = waitFor(app.textFields["Price paid, in dollars"].firstMatch, "the price field")
        price.tap()
        price.typeText("15.50")
        step("filled")
        // The keyboard covers the toolbar on nothing: Save is in the navigation bar.
        element("sheet-save").tap()

        waitUntilGone(app.navigationBars["Add bottle"], "the sheet closes")
        step("arrival")
        let bottle = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'bottle-' AND NOT identifier BEGINSWITH 'bottle-level'")).firstMatch
        waitFor(bottle, "the new bottle's row")
        XCTAssertTrue(bottle.label.contains("Half"), "the row says Half: \(bottle.label)")
        XCTAssertTrue(bottle.label.contains("$15.50"), "the row has the price: \(bottle.label)")
        sleep(2)
        step("row")
        app.swipeUp()
        sleep(1)
        step("row-in-context")
    }
}

/// A bottle's level from Full down to Empty, then archived.
final class BottleLevelFlow: FlowCase {
    @MainActor
    func testBottleLevel() throws {
        // Flakie Holo Taco: one full bottle.
        launch(open: "https://polished.janpuc.com/shades/14")
        let menu = waitFor(element("bottle-level-3"), "the level menu")
        waitForLabel(menu, containing: "Full")
        sleep(2)
        step("full")

        for level in ["Low", "Empty"] {
            choose(level, from: element("bottle-level-3"))
            waitForLabel(element("bottle-level-3"), containing: level)
            sleep(1)
            step("level-\(level.lowercased())")
        }
        waitUntilGone(labelled("Owned ×1"), "empty means the shade is no longer owned")
        step("not-owned")

        element("bottle-3").tap()
        waitFor(app.navigationBars["Edit bottle"], "the Edit bottle sheet")
        step("edit-sheet")
        scrollTo(element("archive-bottle"), "Archive this bottle")
        step("archive")
        element("archive-bottle").tap()
        waitUntilGone(app.navigationBars["Edit bottle"], "the sheet closes")
        waitForLabel(element("bottle-3"), containing: "Archived")
        step("archived")

        tapTab("Bottles")
        let show = waitFor(app.buttons["Show archived"].firstMatch, "Show archived")
        show.tap()
        waitFor(element("bottle-3"), "the archived bottle in the past bottles")
        step("past-bottles")
    }
}

/// The wishlist: the heart on a shade, its priority, then I bought these.
final class WishlistWritesFlow: FlowCase {
    @MainActor
    func testWishlist() throws {
        // Hit The Lights: not owned, not wished.
        launch(open: "https://polished.janpuc.com/shades/3")
        let heart = waitFor(element("wishlist-heart"), "the heart")
        sleep(2)
        step("shade")
        heart.tap()
        waitForLabel(element("wishlist-heart"), containing: "On the wishlist")
        sleep(1)
        step("hearted")

        tapTab("Wishlist")
        waitFor(element("checkout-button"), "the checkout button")
        let menu = app.buttons.matching(NSPredicate(format: "label CONTAINS 'for Hit The Lights'")).firstMatch
        waitFor(menu, "the row's menu")
        step("wishlist")
        choose("Maybe one day", from: menu)
        waitFor(
            app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Maybe one day' AND label CONTAINS '2'")).firstMatch,
            "two shades under Maybe one day")
        sleep(1)
        step("priority")

        let bought = app.buttons["I bought these"].firstMatch
        scrollTo(bought, "I bought these")
        bought.tap()
        waitFor(app.navigationBars["I bought these"], "the I bought these sheet")
        sleep(1)
        step("bought-sheet")
        element("sheet-save").tap()
        waitUntilGone(app.navigationBars["I bought these"], "the sheet closes")
        waitFor(app.staticTexts["Nothing wished yet. Tap the heart on a shade."], "the wishlist is empty")
        step("wishlist-empty")

        tapTab("Bottles")
        let mode = app.segmentedControls["bottles-mode"].firstMatch
        waitFor(mode, "the Collection and History control")
        mode.buttons["History"].tap()
        waitFor(labelled("Hit The Lights, Bought"), "the new bottle in History")
        step("history")
    }
}

/// Make a wheel, then delete it behind a confirmation that says what goes.
final class WheelDeleteFlow: FlowCase {
    @MainActor
    func testWheelDelete() throws {
        launch()
        tapTab("Wheels")
        waitFor(element("wheel-card-\(wheelSlug)"), "the wheel list")
        element("new-wheel").tap()
        let name = waitFor(app.textFields["Name"].firstMatch, "the name field")
        name.tap()
        name.typeText("Jellies")
        let stepper = app.steppers.firstMatch
        waitFor(stepper, "the slot stepper")
        for _ in 0..<8 { element("slot-stepper-Decrement").tap() }
        step("new-wheel")
        element("sheet-save").tap()

        waitFor(element("wheel-ring"), "the new wheel")
        waitFor(app.staticTexts["Jellies"].firstMatch, "its name")
        sleep(1)
        step("wheel-page")
        let delete = element("delete-wheel")
        scrollTo(delete, "the Delete row")
        step("foot")
        delete.tap()

        waitFor(app.staticTexts["Delete Jellies?"], "the confirmation")
        sleep(1)
        step("confirmation")
        element("confirm-delete-wheel").tap()
        waitUntilGone(app.staticTexts["Delete Jellies?"], "the sheet closes")
        waitFor(element("status-line"), "the status line")
        step("gone")
        let card = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Jellies'")).firstMatch
        waitUntilGone(card, "the wheel is gone from the list")
    }
}

/// The Tag page on a device without NFC (a simulator): the QR, the address and Copy, no Write and
/// Check, "Write it from your iPhone"; then the tag's moves: a new URL, and taking another wheel's.
final class TagFlow: FlowCase {
    @MainActor
    func testTag() throws {
        openTag()
        let qr = waitFor(element("tag-qr"), "the QR code")
        XCTAssertTrue(qr.label.contains("/w/\(wheelSlug)"), "the QR is for this wheel: \(qr.label)")
        waitForLabel(element("tag-lede"), containing: "Write it from your iPhone")
        XCTAssertFalse(element("tag-write").exists, "Write to sticker is hidden without NFC")
        XCTAssertFalse(element("tag-check").exists, "Check the sticker is hidden without NFC")
        let address = element("tag-address")
        XCTAssertTrue(address.label.hasSuffix("/w/\(wheelSlug)"), "the address: \(address.label)")
        sleep(1)
        step("tag-page")

        element("tag-copy").tap()
        waitForLabel(element("tag-copy"), containing: "Copied")
        step("copied")

        let newTag = element("new-tag-url")
        scrollTo(newTag, "New tag URL")
        newTag.tap()
        let confirm = dialogButton("New tag URL")
        step("new-tag-confirm")
        confirm.tap()
        waitFor(labelled("New tag URL. Write it"), "the status line")
        let renewed = element("tag-address")
        let deadline = Date().addingTimeInterval(10)
        while renewed.label.hasSuffix("/w/\(wheelSlug)"), Date() < deadline { usleep(300_000) }
        XCTAssertFalse(renewed.label.hasSuffix("/w/\(wheelSlug)"), "the address changed: \(renewed.label)")
        step("new-tag-done")

        let take = element("take-the-tag")
        scrollTo(take, "Take the tag of…")
        take.tap()
        let toppers = waitFor(app.buttons["Toppers"].firstMatch, "Toppers in the sheet")
        step("take-sheet")
        toppers.tap()
        let swap = dialogButton("Take the tag")
        step("take-confirm")
        swap.tap()
        waitFor(labelled("took the tag of Toppers"), "the status line")
        sleep(1)
        step("take-done")
    }
}

/// Writing a sticker and checking it, through the fake sticker of a Debug build (`-nfc ok`): Core
/// NFC itself is device-only (docs/NATIVE.md 6.3). Blank, written, read back; a locked sticker;
/// a sticker that opens another wheel.
final class TagStickerFlow: FlowCase {
    @MainActor
    func testWriteAndCheck() throws {
        openTag(extra: ["-nfc", "ok"])
        let check = waitFor(element("tag-check"), "Check the sticker")
        waitFor(element("tag-write"), "Write to sticker")
        waitForLabel(element("tag-lede"), containing: "A sticker on the wheel opens it here")
        step("tag-page")

        check.tap()
        waitForLabel(element("tag-outcome"), containing: "This sticker is empty")
        step("blank")

        element("tag-write").tap()
        waitForLabel(element("tag-outcome"), containing: "Written. Tap it with your iPhone to open Holos.")
        waitForLabel(element("tag-last-written"), containing: "Written ")
        XCTAssertFalse(element("tag-last-written").label.contains("Not written yet"))
        step("written")

        element("tag-check").tap()
        waitForLabel(element("tag-outcome"), containing: "This sticker opens Holos.")
        step("checked")
        app.terminate()

        openTag(extra: ["-nfc", "readonly"])
        waitFor(element("tag-write"), "Write to sticker").tap()
        waitForLabel(element("tag-outcome"), containing: "This sticker is locked. Use another one.")
        waitFor(app.buttons["Try again"].firstMatch, "Try again after a failure")
        step("locked")
        app.terminate()

        openTag(extra: ["-nfc", "other"])
        waitFor(element("tag-check"), "Check the sticker").tap()
        waitForLabel(element("tag-outcome"), containing: "This sticker opens Toppers, not this wheel")
        step("other-wheel")
    }
}

/// The Scan screen's typed field on a device without a camera: short digits are a name search that
/// finds nothing, a barcode the app knows is a match, forgetting it makes it new, teaching it again, Add bottle, and the learned
/// codes list.
final class ScanTypedFlow: FlowCase {
    @MainActor
    func testScanTyped() throws {
        launch()
        let scanButton = waitFor(element("scan-button"), "Home's scan button")
        scanButton.tap()
        waitFor(element("scan-unavailable"), "the line that says the camera is not here")
        waitFor(element("scan-field"), "the typed field")
        step("scan")

        let field = app.textFields["scan-field"].firstMatch
        field.tap()
        field.typeText("259")
        waitFor(element("scan-no-results"), "a name search for the digits")
        waitForLabel(element("scan-no-results"), containing: "Nothing matches")
        XCTAssertFalse(element("scan-suggestion").exists, "digits that are not a barcode suggest nothing")
        step("short-digits")

        // The card that appeared under the field took the keyboard with it on an iPad.
        if !field.hasKeyboardFocus { field.tap() }
        field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: 3))
        field.typeText("810170284120")
        waitFor(element("scan-lead"), "the known barcode")
        waitForLabel(element("scan-lead"), containing: "Barcode 0810170284120 is")
        step("match")

        element("scan-not-it").tap()
        dialogButton("Forget it").tap()
        waitFor(element("scan-unknown-code"), "the barcode is new again")
        waitForLabel(element("scan-unknown-code"), containing: "New barcode 0810170284120")
        step("unknown-code")

        let learn = app.textFields["learn-field"].firstMatch
        learn.tap()
        learn.typeText("spirit")
        let row = waitFor(element("learn-row-\(spiritFingersID)"), "Spirit Fingers in the picker")
        step("picker")
        row.tap()
        waitFor(element("scan-notice"), "the saved notice")
        waitForLabel(element("scan-notice"), containing: "Saved. 0810170284120 is now Spirit Fingers.")
        step("learned")

        let add = waitFor(element("scan-add"), "Add bottle")
        // The picker's field is still up: its key (Search) closes the keyboard, then Add bottle.
        let key = app.keyboards.buttons.matching(NSPredicate(format: "label IN {'Search','search','Return','return','Done'}")).firstMatch
        if key.waitForExistence(timeout: 2) { key.tap() }
        add.tap()
        waitFor(app.navigationBars["Add bottle"], "the Add bottle sheet")
        step("add-bottle")
        element("sheet-save").tap()
        // The status line is short-lived: it is looked for first, the closing of the cover after it.
        waitFor(labelled("Added Spirit Fingers"), "the status line")
        waitUntilGone(element("scan-field"), "the scan screen closes after the bottle is added")
        step("added")

        // The learned codes: Settings on a phone (the mark on Home), the sidebar's tab on an iPad.
        if element("settings-button").waitForExistence(timeout: 3) {
            element("settings-button").tap()
        } else {
            tapTab("Settings")
        }
        let learned = element("learned-codes")
        scrollTo(learned, "Learned codes in Settings")
        learned.tap()
        let code = waitFor(element("learned-list"), "the learned codes")
        waitFor(labelled("Barcode 0810170284120"), "the barcode just taught")
        step("learned-codes")
        let first = app.cells.containing(NSPredicate(format: "label CONTAINS 'Barcode 0810170284120'")).firstMatch
        waitFor(first, "the barcode's row")
        first.swipeLeft()
        let forget = waitFor(app.buttons["Forget"].firstMatch, "the swipe's Forget button")
        step("swipe")
        forget.tap()
        waitUntilGone(labelled("Barcode 0810170284120"), "the barcode is forgotten")
        // It was the only learned code: the list gives way to the empty line.
        waitFor(element("learned-empty"), "nothing learned any more")
        XCTAssertFalse(code.exists)
        step("forgotten")
    }
}

/// "I wore this" and "Another" on Home.
final class WearFlow: FlowCase {
    @MainActor
    func testWear() throws {
        launch()
        let wore = waitFor(element("wore-button"), "I wore this")
        sleep(2)
        step("home")
        wore.tap()
        waitFor(element("worn-today"), "Worn today")
        step("worn")
        element("another-button").tap()
        sleep(1)
        step("another")
    }
}

/// The tip colour of a shade: set (here from the hex field; the system colour picker is a
/// remote view XCUITest cannot drive), the tip changes, then reset.
final class TipColourFlow: FlowCase {
    @MainActor
    func testTipColour() throws {
        launch(open: "https://polished.janpuc.com/shades/\(spiritFingersID)")
        waitFor(app.staticTexts["Spirit Fingers"].firstMatch, "the shade page")
        sleep(2)
        step("before")
        let section = app.buttons["Tip colour"].firstMatch
        scrollTo(section, "the Tip colour section")
        section.tap()
        waitFor(app.buttons["Pick a colour"].firstMatch, "the colour picker")
        let hex = app.textFields["tip-colour-hex"].firstMatch
        scrollTo(hex, "the hex field")
        step("section")
        hex.tap()
        // Editing starts with the old colour selected, so typing replaces it.
        hex.typeText("#7a3fd1\n")
        waitFor(app.staticTexts["Set by you"].firstMatch, "the colour is set")
        XCTAssertEqual(hex.value as? String, "#7a3fd1")
        sleep(1)
        step("set")
        app.swipeDown(velocity: .fast)
        app.swipeDown(velocity: .fast)
        app.swipeDown(velocity: .fast)
        sleep(2)
        step("tip-changed")

        let reset = app.buttons["tip-colour-reset"].firstMatch
        scrollTo(reset, "Reset")
        XCTAssertTrue(reset.isEnabled, "Reset is on once the colour is set")
        reset.tap()
        waitFor(app.staticTexts["Read from the photos"].firstMatch, "back to the sampled colour")
        sleep(1)
        step("reset")
        app.swipeDown(velocity: .fast)
        app.swipeDown(velocity: .fast)
        app.swipeDown(velocity: .fast)
        sleep(2)
        step("tip-back")
    }
}

// MARK: The builder (run 4)

extension FlowCase {
    /// A ring slot by its number (its label starts "Slot 11").
    @MainActor
    func slot(_ position: Int) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "Slot \(position),")).firstMatch
    }

    /// The builder for `position`, opened from the ring of the wheel the link names.
    @MainActor
    func openBuilder(slot position: Int) {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)")
        waitFor(element("wheel-ring"), "the ring")
        sleep(1)
        waitFor(slot(position), "slot \(position)").tap()
        waitFor(app.staticTexts["Slot \(position)"].firstMatch, "the builder")
    }

    /// Types into the builder's search field (a fresh simulator introduces slide-to-type first).
    @MainActor
    func typeInBuilder(_ text: String) {
        let field = waitFor(app.textFields["builder-search"].firstMatch, "the builder's search field")
        field.tap()
        field.typeText(text)
        let introduction = app.buttons["Continue"]
        if introduction.waitForExistence(timeout: 1) { introduction.tap() }
    }

    @MainActor
    func button(_ label: String) -> XCUIElement {
        waitFor(app.buttons[label].firstMatch, label)
    }

    /// The row of a layer in the builder by its shade's name (its label is "Top, Flakie Holo Taco, 2 coats").
    @MainActor
    func layerRow(_ title: String) -> XCUIElement {
        app.descendants(matching: .any).matching(
            NSPredicate(format: "identifier BEGINSWITH 'layer-row-' AND label CONTAINS %@", title)
        ).firstMatch
    }

    /// Taps the layer's row and steps its coats to `count` in the popover, then closes the popover.
    @MainActor
    func setCoats(of title: String, to count: Int) {
        let row = waitFor(layerRow(title), "the row of \(title)")
        row.tap()
        // A tap that lands while the list is still settling after the keyboard went away does nothing.
        if !element("layer-coats").waitForExistence(timeout: 4) { row.tap() }
        let stepper = waitFor(element("layer-coats"), "the coats stepper")
        while true {
            let shown = Int(stepper.label.filter(\.isNumber)) ?? Int(String(describing: stepper.value ?? "")) ?? 0
            if shown >= count { break }
            // The stepper is one element; its plus is the right end of the control.
            stepper.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()
            waitForLabel(layerRow(title), containing: "\(shown + 1) coat")
        }
        closePopover()
    }

    /// The search key of the keyboard closes it, as a person would, and the list goes back to its top.
    @MainActor
    func closeKeyboard() {
        let key = app.keyboards.buttons.matching(NSPredicate(format: "label IN {'Search','search','Return','return','Done'}")).firstMatch
        if key.waitForExistence(timeout: 2) { key.tap() }
        app.swipeDown()
        sleep(1)
    }

    /// A tap on the dimmed rest of the screen closes a popover.
    @MainActor
    func closePopover() {
        let dismiss = app.otherElements["PopoverDismissRegion"].firstMatch
        if dismiss.waitForExistence(timeout: 2) {
            dismiss.tap()
        } else {
            element("builder-summary").tap()
        }
        waitUntilGone(element("layer-coats"), "the popover closes")
    }

    /// The hub of the ring says which slot is being edited, and the slot is lifted and named for what the draft holds.
    @MainActor
    func assertRingEditing(_ position: Int, containing shade: String? = nil) {
        waitForLabel(element("wheel-hub"), containing: "Editing slot \(position)")
        if let shade { waitForLabel(slot(position), containing: shade) }
    }

    /// Leaves the builder open on the screen and keeps its draft: the inspector's Close, a sheet's drag.
    @MainActor
    func closeBuilderKeepingDraft() {
        let close = element("builder-close")
        if close.waitForExistence(timeout: 2) {
            close.tap()
        } else {
            // The sheet comes down by its top bar, between Cancel and Save: from .large to .medium
            // (where it opens), then away. A drag above it would land on the page behind.
            let window = app.windows.firstMatch
            for _ in 0..<3 where element("builder-save").exists {
                let bar = element("builder-save").frame.midY / window.frame.height
                let top = window.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: bar))
                top.press(forDuration: 0.1, thenDragTo: window.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.98)))
                sleep(1)
            }
        }
        waitUntilGone(element("builder-save"), "the builder closes")
    }
}

/// Slot 11, empty: the sheet opens at its middle detent with the ring in view and slot 11 lifted;
/// Over black, search "flak", add it (the ring slot paints it), a second coat from the popover,
/// press and drag a layer to reorder, Done, Save swatch.
final class BuilderFlow: FlowCase {
    @MainActor
    func testBuilder() throws {
        openBuilder(slot: 11)
        sleep(1)
        assertRingEditing(11)
        step("opened")

        if UIDevice.current.userInterfaceIdiom == .pad {
            // The sidebar folds while the builder is open in both orientations and the ring keeps
            // its room (read in the screenshots). The builder is closed (the draft stays) before
            // each turn and opened again after it.
            closeBuilderKeepingDraft()
            XCUIDevice.shared.orientation = .landscapeLeft
            sleep(2)
            waitFor(slot(11), "slot 11 in landscape").tap()
            waitFor(app.staticTexts["Slot 11"].firstMatch, "the builder in landscape")
            waitFor(element("builder-save"), "the builder's actions in landscape")
            sleep(1)
            step("opened-landscape")
            closeBuilderKeepingDraft()
            XCUIDevice.shared.orientation = .portrait
            sleep(2)
            waitFor(slot(11), "slot 11 in portrait again").tap()
            waitFor(app.staticTexts["Slot 11"].firstMatch, "the builder in portrait again")
            sleep(1)
        }

        button("Over black").tap()
        waitFor(layerRow("One-Coat Black"), "One-Coat Black as the base")
        assertRingEditing(11, containing: "One-Coat Black")
        sleep(1)
        step("over-black")

        // The popover on the base, at the middle detent: coats and Remove.
        waitFor(layerRow("One-Coat Black"), "the base row").tap()
        waitFor(element("layer-coats"), "the coats stepper")
        step("popover")
        closePopover()

        typeInBuilder("flak")
        let add = waitFor(app.buttons["Add Flakie Holo Taco"].firstMatch, "Flakie Holo Taco in the results")
        step("searching")
        add.tap()
        waitFor(layerRow("Flakie Holo Taco"), "Flakie Holo Taco as the top layer")
        assertRingEditing(11, containing: "Flakie Holo Taco")
        waitForLabel(layerRow("Flakie Holo Taco"), containing: "1 coat")
        sleep(1)
        step("added")
        closeKeyboard()

        setCoats(of: "Flakie Holo Taco", to: 2)
        waitForLabel(element("builder-summary"), containing: "Flakie Holo Taco ×2")
        sleep(1)
        step("two-coats")

        // Press and drag the top layer above the base.
        layerRow("Flakie Holo Taco").press(forDuration: 0.6, thenDragTo: layerRow("One-Coat Black"))
        waitFor(element("layers-done"), "Done while arranging")
        waitForLabel(element("builder-summary"), containing: "Flakie Holo Taco ×2 + One-Coat Black")
        sleep(1)
        step("arranging")
        element("layers-done").tap()
        waitUntilGone(element("layers-done"), "Done goes away")
        waitForLabel(element("builder-summary"), containing: "Flakie Holo Taco ×2 + One-Coat Black")
        sleep(1)
        step("rearranged")

        // And back, then a tap outside the layers ends arranging as well.
        layerRow("Flakie Holo Taco").press(forDuration: 0.6, thenDragTo: layerRow("One-Coat Black"))
        waitForLabel(element("builder-summary"), containing: "One-Coat Black + Flakie Holo Taco ×2")
        waitFor(element("layers-done"), "Done while arranging again")
        element("builder-summary").tap()
        waitUntilGone(element("layers-done"), "a tap outside ends arranging")
        sleep(1)
        step("restored")

        button("Save swatch").tap()
        waitUntilGone(element("builder-save"), "the builder closes")
        step("saved")
        let row = waitFor(element("swatch-row-11"), "the Swatches row of slot 11")
        waitForLabel(row, containing: "One-Coat Black + Flakie Holo Taco ×2")
        waitForLabel(slot(11), containing: "One-Coat Black + Flakie Holo Taco ×2")
        XCTAssertFalse(element("wheel-hub").label.contains("Editing"), "the hub is the count again")
        sleep(2)
        step("tile-filled")
    }
}

/// The same arranging under Reduce Motion (the launch argument stands in for the setting): the
/// rows do not jiggle or lift, each shows a handle, and the drag still reorders.
final class BuilderReducedMotionFlow: FlowCase {
    @MainActor
    func testReducedMotion() throws {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)", extra: ["-reducemotion", "1"])
        waitFor(element("wheel-ring"), "the ring")
        sleep(1)
        waitFor(slot(11), "slot 11").tap()
        waitFor(app.staticTexts["Slot 11"].firstMatch, "the builder")
        assertRingEditing(11)
        button("Over black").tap()
        waitFor(layerRow("One-Coat Black"), "One-Coat Black")
        typeInBuilder("flak")
        app.buttons["Add Flakie Holo Taco"].firstMatch.tap()
        waitFor(layerRow("Flakie Holo Taco"), "Flakie Holo Taco")
        closeKeyboard()
        layerRow("One-Coat Black").press(forDuration: 0.6, thenDragTo: layerRow("Flakie Holo Taco"))
        waitFor(element("layers-done"), "Done while arranging")
        waitForLabel(element("builder-summary"), containing: "Flakie Holo Taco + One-Coat Black")
        sleep(1)
        step("handles")
        element("layers-done").tap()
        waitUntilGone(element("layers-done"), "Done goes away")
        element("builder-cancel").tap()
        waitUntilGone(element("builder-save"), "the builder closes")
    }
}

/// Copy from… (a saved swatch's layers), then Same as last, then Cancel: slot 10 stays empty.
final class BuilderCopyFlow: FlowCase {
    @MainActor
    func testCopy() throws {
        openBuilder(slot: 10)
        sleep(1)
        button("Copy from…").tap()
        waitFor(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'copy-source-'")).firstMatch, "saved swatches to copy")
        sleep(1)
        step("copy-sources")
        // The list is long: search it, as a person would.
        let field = waitFor(app.searchFields.firstMatch, "the search field of the list")
        field.tap()
        field.typeText("flakie")
        let source = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Spirit Fingers' AND label CONTAINS 'Flakie'")).firstMatch
        waitFor(source, "the Spirit Fingers + Flakie swatch")
        step("copy-search")
        source.tap()
        waitForLabel(element("builder-summary"), containing: "Spirit Fingers")
        assertRingEditing(10, containing: "Spirit Fingers")
        sleep(1)
        step("copied")

        button("Same as last").tap()
        waitForLabel(element("builder-summary"), containing: "Magnetic Taco")
        sleep(1)
        step("same-as-last")

        element("builder-cancel").tap()
        waitUntilGone(element("builder-save"), "the builder closes")
        waitForLabel(slot(10), containing: "empty")
        sleep(1)
        step("discarded")
    }
}

/// Start, close, open again: "Resumed your draft"; Cancel throws it away.
final class BuilderResumeFlow: FlowCase {
    @MainActor
    func testResume() throws {
        openBuilder(slot: 10)
        button("Over black").tap()
        waitFor(layerRow("One-Coat Black"), "One-Coat Black")
        XCTAssertFalse(element("builder-resumed").exists, "a new draft is not a resumed one")
        step("started")
        closeBuilderKeepingDraft()
        waitForLabel(slot(10), containing: "draft in progress")
        sleep(1)
        step("draft-on-the-ring")

        slot(10).tap()
        waitFor(element("builder-resumed"), "Resumed your draft")
        waitForLabel(element("builder-summary"), containing: "One-Coat Black")
        assertRingEditing(10, containing: "One-Coat Black")
        sleep(1)
        step("resumed")

        element("builder-cancel").tap()
        waitUntilGone(element("builder-save"), "the builder closes")
        waitForLabel(slot(10), containing: "empty")
        step("cancelled")
        slot(10).tap()
        waitFor(app.staticTexts["Slot 10"].firstMatch, "the builder again")
        sleep(1)
        XCTAssertFalse(element("builder-resumed").exists, "Cancel threw the draft away")
        step("fresh")
    }
}

extension FlowCase {
    /// The wheel by its link, then Tag and QR from its foot.
    @MainActor
    func openTag(extra: [String] = []) {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)", extra: extra)
        let row = element("tag-and-qr")
        scrollTo(row, "Tag and QR")
        row.tap()
        waitFor(app.navigationBars["Tag and QR code"], "the Tag page")
    }
}
