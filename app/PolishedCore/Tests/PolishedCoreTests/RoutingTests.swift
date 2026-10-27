import Foundation
import PolishedAPI
import PolishedModels
import PolishedStore
import Testing

@Suite("Deep links")
struct DeepLinkTests {
    private func link(_ text: String) -> DeepLink? { DeepLink(url: URL(string: text)!) }

    @Test func wheel() {
        #expect(link("https://polished.janpuc.com/w/k3m9xq") == .wheel(slug: "k3m9xq"))
        #expect(link("https://polished.janpuc.com/w/k3m9xq/") == .wheel(slug: "k3m9xq"))
        #expect(link("http://127.0.0.1:8080/w/7b2vdc?x=1") == .wheel(slug: "7b2vdc"))
    }

    @Test func shade() {
        #expect(link("https://polished.janpuc.com/shades/13") == .shade(id: 13))
    }

    @Test("a slug outside the server's alphabet is rejected", arguments: [
        "https://polished.janpuc.com/w/K3M9XQ", "https://polished.janpuc.com/w/../x", "https://polished.janpuc.com/w/k3m9x",
        "https://polished.janpuc.com/w/k3m9xqq", "https://polished.janpuc.com/w/k3m9xl", "https://polished.janpuc.com/w/",
    ])
    func badSlug(_ text: String) {
        #expect(link(text) == nil)
    }

    @Test("an id that is not plain digits is rejected", arguments: [
        "https://polished.janpuc.com/shades/abc", "https://polished.janpuc.com/shades/new", "https://polished.janpuc.com/shades/-1",
        "https://polished.janpuc.com/shades/0", "https://polished.janpuc.com/shades/1.5", "https://polished.janpuc.com/shades/",
        "https://polished.janpuc.com/shades/1234567890",
    ])
    func badId(_ text: String) {
        #expect(link(text) == nil)
    }

    @Test func otherPathsAndSchemesAreIgnored() {
        #expect(link("https://polished.janpuc.com/wishlist") == nil)
        #expect(link("https://polished.janpuc.com/auth/app/callback?code=x") == nil)
        #expect(link("polished://w/k3m9xq") == nil)
        #expect(link("https://polished.janpuc.com/") == nil)
    }
}

@Suite("PKCE")
struct PKCETests {
    @Test("the RFC 7636 appendix B vector")
    func rfcVector() {
        #expect(PKCE.challenge(for: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
    }

    @Test func verifierIsBase64URLOf32Bytes() {
        let verifier = PKCE.makeVerifier()
        #expect(verifier.count == 43)
        #expect(verifier.allSatisfy { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" })
        #expect(verifier != PKCE.makeVerifier())
    }
}

@Suite("Ring geometry")
struct RingGeometryTests {
    private let ring = RingGeometry(slotCount: 20, radius: 150, slotHeight: 62)

    @Test func slotOneIsAtTwelveAndTheNumbersRunClockwise() {
        let first = ring.offset(for: 1)
        #expect(abs(first.x) < 1e-9)
        #expect(abs(first.y + 150) < 1e-9)
        let sixth = ring.offset(for: 6)  // a quarter turn: three o'clock
        #expect(abs(sixth.x - 150) < 1e-9)
        #expect(abs(sixth.y) < 1e-9)
        let eleventh = ring.offset(for: 11)  // half a turn: six o'clock
        #expect(abs(eleventh.y - 150) < 1e-9)
    }

    @Test func slotWidthIsTheTipsOwnUntilTheRingIsCrowded() {
        #expect(abs(ring.slotWidth - 38.006) < 0.01)
        #expect(RingGeometry(slotCount: 40, radius: 150, slotHeight: 62).slotWidth < 38)
        #expect(ring.diameter == 362)
    }

    @Test func lightIsTurnedBackByTheSlotAngle() {
        let screen = (x: -0.35, y: -0.55)
        let top = ring.light(for: 1, screen: screen)
        #expect(top.x == -0.35 && top.y == -0.55)
        // At three o'clock the tip is turned 90 degrees clockwise: screen "up" is its left.
        let right = ring.light(for: 6, screen: screen)
        #expect(abs(right.x - (-0.55)) < 1e-9)
        #expect(abs(right.y - 0.35) < 1e-9)
    }
}

@Suite("Router")
@MainActor
struct RouterTests {
    private func url(_ text: String) -> URL { URL(string: text)! }

    @Test func aWheelLinkOpensTheWheelsTab() {
        let router = Router()
        router.handle(url("https://polished.janpuc.com/w/k3m9xq"), signedIn: true)
        #expect(router.tab == .wheels)
        #expect(router.path(.wheels) == [.wheel(slug: "k3m9xq")])
    }

    @Test func aShadeLinkOpensTheShadesTab() {
        let router = Router()
        router.handle(url("https://polished.janpuc.com/shades/13"), signedIn: true)
        #expect(router.tab == .shades)
        #expect(router.path(.shades) == [.shade(13)])
    }

    @Test func aLinkThatIsNotOursChangesNothing() {
        let router = Router()
        router.handle(url("https://polished.janpuc.com/w/NOPE"), signedIn: true)
        router.handle(url("https://polished.janpuc.com/shades/abc"), signedIn: false)
        #expect(router.tab == .home)
        #expect(router.pendingLink == nil)
        #expect(router.paths.isEmpty)
    }

    @Test func signedOutTheLinkWaitsForSignIn() {
        let router = Router()
        router.handle(url("https://polished.janpuc.com/w/k3m9xq"), signedIn: false)
        #expect(router.tab == .home)
        #expect(router.pendingLink == .wheel(slug: "k3m9xq"))
        router.openPending()
        #expect(router.pendingLink == nil)
        #expect(router.path(.wheels) == [.wheel(slug: "k3m9xq")])
        router.openPending()  // nothing left to open
        #expect(router.tab == .wheels)
    }

    @Test func homeShortcutsOpenShadesWithAQuery() {
        let router = Router()
        var query = ShadeQuery()
        query.kind = "topper"
        router.paths[.shades] = [.shade(3)]
        router.showShades(query, focusSearch: true)
        #expect(router.tab == .shades)
        #expect(router.shadesPreset?.kind == "topper")
        #expect(router.focusSearch)
        #expect(router.path(.shades).isEmpty)
    }
}
