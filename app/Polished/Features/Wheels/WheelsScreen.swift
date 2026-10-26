import SwiftUI

/// Wheels as a placeholder: the empty state, the unpainted tip and one action.
struct WheelsScreen: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                EmptyState(line: "No wheels yet.", action: "Make one")
                    .padding(.top, 48)
            }
            .background(Color.board)
            .navigationTitle("Wheels")
        }
    }
}
