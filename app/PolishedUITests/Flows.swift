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
