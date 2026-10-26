import SwiftUI

/// The shelf a rack of tips stands on: a 1.5 pt Line rule across the full width, with a 10 pt
/// fade of shadow ink at 8% under it. The tips' contact shadows rest on the rule.
struct Ledge: View {
    var body: some View {
        VStack(spacing: 0) {
            Rectangle()
                .fill(Color.line)
                .frame(height: 1.5)
            LinearGradient(colors: [Color.shadowInk.opacity(0.08), .clear], startPoint: .top, endPoint: .bottom)
                .frame(height: 10)
        }
        .accessibilityHidden(true)
    }
}
