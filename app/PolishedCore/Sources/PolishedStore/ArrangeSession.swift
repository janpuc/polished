import Foundation

/// The state of arranging the layers by hand (docs/NATIVE.md 5.7), apart from any gesture: the
/// view feeds it what a finger did (a hold, a drag, a lift) and acts on what it answers. Rows are
/// named by their index in the stack; the view keeps the layer behind the held index.
public struct ArrangeSession: Equatable, Sendable {
    /// The rows jiggle and a plain drag picks one up.
    public private(set) var isArranging = false
    /// The row in the hand, nil between drags.
    public private(set) var held: Held?

    public struct Held: Equatable, Sendable {
        public let from: Int
        /// How far the finger has moved down (negative: up) since the row was picked up.
        public var translation: Double
        /// The index the row would land on if it were dropped now.
        public var target: Int

        public init(from: Int, translation: Double, target: Int) {
            self.from = from
            self.translation = translation
            self.target = target
        }
    }

    /// What the view does about an input: a haptic, or the moves to send to the model.
    public enum Event: Equatable, Sendable {
        case none
        /// Arranging began, or a row was picked up: the selection haptic.
        case pickedUp
        /// The held row passed another: the selection haptic.
        case crossed
        /// The row was let go: the medium impact, and these `move(_, up:)` calls in order.
        case dropped(moves: [Bool])
    }

    public init() {}

    /// The "Arrange" button: the rows jiggle, nothing is picked up yet.
    public mutating func begin(count: Int) -> Event {
        guard count >= 2, !isArranging else { return .none }
        isArranging = true
        return .pickedUp
    }

    /// A long press held on the row at `index` was recognised: arranging starts and the row is picked up.
    public mutating func hold(at index: Int, count: Int) -> Event {
        guard count >= 2, (0..<count).contains(index) else { return .none }
        isArranging = true
        return pickUp(index)
    }

    /// A plain drag began on the row at `index`. Only while arranging: otherwise the drag is a scroll.
    public mutating func dragBegan(at index: Int, count: Int) -> Event {
        guard isArranging, (0..<count).contains(index) else { return .none }
        return pickUp(index)
    }

    /// The finger moved: the held row follows, and `.crossed` when it passed another row.
    public mutating func dragMoved(translation: Double, count: Int, rowHeight: Double) -> Event {
        guard var current = held else { return .none }
        let target = BuilderArrangement.target(
            from: current.from, translation: translation, count: count, rowHeight: rowHeight)
        let crossed = target != current.target
        current.translation = translation
        current.target = target
        held = current
        return crossed ? .crossed : .none
    }

    /// The finger lifted, or the touch was cancelled: the held row is dropped where it is.
    public mutating func dragEnded() -> Event {
        guard let current = held else { return .none }
        held = nil
        return .dropped(moves: BuilderArrangement.moves(from: current.from, target: current.target))
    }

    /// Done, a tap outside the layers, Save, Cancel or the sheet closing.
    public mutating func done() {
        isArranging = false
        held = nil
    }

    /// A stack of fewer than two rows has nothing to arrange.
    public mutating func layerCountChanged(to count: Int) {
        if count < 2 { done() }
    }

    /// Whether a tap on a row opens its popover (it does not while arranging).
    public var opensPopover: Bool { !isArranging }

    private mutating func pickUp(_ index: Int) -> Event {
        guard held == nil else { return .none }
        held = Held(from: index, translation: 0, target: index)
        return .pickedUp
    }
}
