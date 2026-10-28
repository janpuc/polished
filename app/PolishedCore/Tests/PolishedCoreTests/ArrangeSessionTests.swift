import PolishedStore
import Testing

@Suite("Arrange session")
struct ArrangeSessionTests {
    private let row = 52.0

    @Test("a hold on a row starts arranging and picks it up")
    func hold() {
        var session = ArrangeSession()
        #expect(!session.isArranging)
        #expect(session.hold(at: 1, count: 3) == .pickedUp)
        #expect(session.isArranging)
        #expect(session.held == ArrangeSession.Held(from: 1, translation: 0, target: 1))
    }

    @Test("a stack of one layer, or a row that is not there, has nothing to arrange")
    func nothingToArrange() {
        var session = ArrangeSession()
        #expect(session.hold(at: 0, count: 1) == .none)
        #expect(session.hold(at: 5, count: 3) == .none)
        #expect(session.begin(count: 1) == .none)
        #expect(!session.isArranging)
    }

    @Test("a plain drag picks a row up only while arranging")
    func plainDrag() {
        var session = ArrangeSession()
        #expect(session.dragBegan(at: 0, count: 3) == .none)
        #expect(session.held == nil)
        #expect(session.begin(count: 3) == .pickedUp)
        #expect(session.isArranging && session.held == nil)
        #expect(session.dragBegan(at: 2, count: 3) == .pickedUp)
        #expect(session.held?.from == 2)
    }

    @Test("the held row crosses its neighbours and the drop sends one move per row")
    func dragAndDrop() {
        var session = ArrangeSession()
        _ = session.hold(at: 0, count: 3)
        #expect(session.dragMoved(translation: 20, count: 3, rowHeight: row) == .none)
        #expect(session.dragMoved(translation: 30, count: 3, rowHeight: row) == .crossed)
        #expect(session.dragMoved(translation: 40, count: 3, rowHeight: row) == .none)
        #expect(session.dragMoved(translation: 120, count: 3, rowHeight: row) == .crossed)
        #expect(session.held?.target == 2)
        #expect(session.dragEnded() == .dropped(moves: [false, false]))
        #expect(session.held == nil)
        #expect(session.isArranging, "dropping leaves the rows jiggling until Done")
    }

    @Test("dragging back to where it started drops with no moves")
    func dragBack() {
        var session = ArrangeSession()
        _ = session.hold(at: 2, count: 3)
        _ = session.dragMoved(translation: -60, count: 3, rowHeight: row)
        #expect(session.held?.target == 1)
        _ = session.dragMoved(translation: 4, count: 3, rowHeight: row)
        #expect(session.dragEnded() == .dropped(moves: []))
    }

    @Test("a drag stays inside the stack")
    func clamped() {
        var session = ArrangeSession()
        _ = session.hold(at: 1, count: 3)
        _ = session.dragMoved(translation: -900, count: 3, rowHeight: row)
        #expect(session.held?.target == 0)
        #expect(session.dragEnded() == .dropped(moves: [true]))
    }

    @Test("a second pick-up while a row is held changes nothing")
    func onlyOneHeld() {
        var session = ArrangeSession()
        _ = session.hold(at: 0, count: 3)
        #expect(session.dragBegan(at: 2, count: 3) == .none)
        #expect(session.held?.from == 0)
        #expect(session.dragEnded() != .none)
        #expect(session.dragEnded() == .none)
    }

    @Test("Done, and a stack that shrinks below two rows, end arranging and let go of the row")
    func ending() {
        var session = ArrangeSession()
        _ = session.hold(at: 0, count: 3)
        session.done()
        #expect(!session.isArranging && session.held == nil)

        _ = session.begin(count: 2)
        session.layerCountChanged(to: 2)
        #expect(session.isArranging)
        session.layerCountChanged(to: 1)
        #expect(!session.isArranging)
    }

    @Test("a tap opens the popover only when the rows are still")
    func tap() {
        var session = ArrangeSession()
        #expect(session.opensPopover)
        _ = session.begin(count: 2)
        #expect(!session.opensPopover)
    }
}
