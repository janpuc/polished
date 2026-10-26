/// How much is left in a bottle.
public enum BottleState: String, Codable, Sendable, CaseIterable {
    case full, half, low, empty

    /// The share of the level arc drawn.
    public var fraction: Double {
        switch self {
        case .full: 1
        case .half: 0.5
        case .low: 0.25
        case .empty: 0
        }
    }

    public var label: String {
        switch self {
        case .full: "Full"
        case .half: "Half"
        case .low: "Low"
        case .empty: "Empty"
        }
    }
}
