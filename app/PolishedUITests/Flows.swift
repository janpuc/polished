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

/// The tag's moves: a new URL, and taking another wheel's tag.
final class WheelTagFlow: FlowCase {
    @MainActor
    func testWheelTag() throws {
        launch(open: "https://polished.janpuc.com/w/\(wheelSlug)")
        let newTag = element("new-tag-url")
        scrollTo(newTag, "New tag URL")
        newTag.tap()
        let confirm = dialogButton("New tag URL")
        step("new-tag-confirm")
        confirm.tap()
        waitFor(labelled("New tag URL. Write it"), "the status line")
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
        step("take-done")
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
