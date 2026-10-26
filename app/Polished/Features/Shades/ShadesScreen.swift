import SwiftUI

/// Shades as a placeholder: rows of tip-m, the name and the finishes.
struct ShadesScreen: View {
    var body: some View {
        NavigationStack {
            List(SampleShade.all) { shade in
                HStack(spacing: 12) {
                    TipView(shade.recipe, size: .m)
                        .padding(.vertical, 6)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(shade.name)
                            .font(.headline)
                            .foregroundStyle(Color.ink)
                        Text(shade.detail)
                            .font(.subheadline)
                            .foregroundStyle(Color.ink2)
                    }
                }
                .listRowBackground(Color.surface)
                .accessibilityElement(children: .combine)
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Shades")
        }
    }
}
