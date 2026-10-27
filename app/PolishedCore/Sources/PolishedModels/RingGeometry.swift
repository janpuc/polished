import Foundation

/// Where the slots of a wheel stand (the web's ring, `app.css` section 15): slot 1 at twelve
/// o'clock, the numbers running clockwise, each tip turned to point away from the centre. A
/// slot's width is the tip's own (0.613 of its height) unless the ring is crowded, then the
/// space it has on the circle less 2.
public struct RingGeometry: Sendable, Equatable {
    public var slotCount: Int
    /// From the centre of the ring to the centre of a slot.
    public var radius: Double
    public var slotHeight: Double

    public init(slotCount: Int, radius: Double, slotHeight: Double) {
        self.slotCount = max(1, slotCount)
        self.radius = radius
        self.slotHeight = slotHeight
    }

    public var slotWidth: Double {
        min(slotHeight * 0.613, 2 * .pi * radius / Double(slotCount) - 2)
    }

    /// The side of the square that holds the ring and its outermost tips.
    public var diameter: Double { 2 * radius + slotHeight }

    /// Clockwise from twelve o'clock, in radians, for a 1-based position.
    public func angle(for position: Int) -> Double {
        2 * .pi / Double(slotCount) * Double(position - 1)
    }

    /// The slot's centre relative to the ring's centre, y down.
    public func offset(for position: Int) -> (x: Double, y: Double) {
        let angle = angle(for: position)
        return (radius * sin(angle), -radius * cos(angle))
    }

    /// The light as the slot's own frame sees it: a tip turned by the slot's angle is lit from
    /// the same side of the screen as every other, so the screen-space light is turned back by
    /// the angle (the web's `--lx`, `--ly`).
    public func light(for position: Int, screen: (x: Double, y: Double)) -> (x: Double, y: Double) {
        let angle = angle(for: position)
        let c = cos(angle), s = sin(angle)
        return (c * screen.x + s * screen.y, -s * screen.x + c * screen.y)
    }
}
