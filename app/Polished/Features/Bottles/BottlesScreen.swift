import PolishedModels
import SwiftUI

/// Bottles as a placeholder: a row per bottle with its level arc and the level in words.
struct BottlesScreen: View {
    private struct Row: Identifiable {
        var id: Int { shade.id }
        var shade: SampleShade
        var state: BottleState
        var bought: String
    }

    private let rows = [
        Row(shade: .acidDrip, state: .half, bought: "Bought 21 Jul 2026, $15.50"),
        Row(shade: .spiritFingers, state: .full, bought: "Bought 3 Aug 2026, $15.50"),
        Row(shade: .castASpell, state: .low, bought: "Bought 2 Mar 2026, $14.00"),
        Row(shade: .blackout, state: .empty, bought: "Bought 9 Jan 2026, $12.00"),
    ]

    var body: some View {
        NavigationStack {
            List(rows) { row in
                HStack(spacing: 12) {
                    TipView(row.shade.recipe, size: .m)
                        .padding(.vertical, 6)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.shade.name)
                            .font(.headline)
                            .foregroundStyle(Color.ink)
                        Text(row.bought)
                            .font(.subheadline)
                            .foregroundStyle(Color.ink)
                    }
                    Spacer(minLength: 8)
                    HStack(spacing: 6) {
                        LevelArc(fraction: row.state.fraction)
                        Text(row.state.label)
                            .font(.subheadline)
                            .foregroundStyle(row.state == .empty ? Color.bad : row.state == .low ? Color.warn : Color.ink)
                            .frame(minWidth: 44, alignment: .leading)
                    }
                }
                .listRowBackground(Color.surface)
                .accessibilityElement(children: .combine)
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Bottles")
        }
    }
}
