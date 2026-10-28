import Foundation

/// The arithmetic of arranging the layers by hand (docs/NATIVE.md 5.7): a row dragged by a
/// distance lands on an index, and the rows it passes shift by one row height to make room.
public enum BuilderArrangement {
    /// The index a row picked up at `from` lands on after being dragged `translation` points
    /// down (negative: up) in a stack of `count` rows of `rowHeight`.
    public static func target(from: Int, translation: Double, count: Int, rowHeight: Double) -> Int {
        guard count > 0, rowHeight > 0 else { return from }
        let moved = from + Int((translation / rowHeight).rounded())
        return min(max(moved, 0), count - 1)
    }

    /// How far the row at `index` is shifted while the row picked up at `from` is over `target`:
    /// a row the dragged one passed moves one row height out of its way.
    public static func reflow(index: Int, from: Int, target: Int, rowHeight: Double) -> Double {
        if from < target, index > from, index <= target { return -rowHeight }
        if from > target, index < from, index >= target { return rowHeight }
        return 0
    }

    /// The `model.move(_, up:)` calls that carry a row from `from` to `target`: `up` is towards
    /// the base (a smaller index). Empty when the row did not change place.
    public static func moves(from: Int, target: Int) -> [Bool] {
        Array(repeating: target < from, count: abs(target - from))
    }
}
