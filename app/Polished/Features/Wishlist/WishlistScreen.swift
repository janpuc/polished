import SwiftUI

/// Wishlist as a placeholder: the empty state.
struct WishlistScreen: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                EmptyState(line: "Nothing wished yet. Tap the heart on a shade.")
                    .padding(.top, 48)
            }
            .background(Color.board)
            .navigationTitle("Wishlist")
        }
    }
}
