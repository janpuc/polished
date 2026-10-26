import NailTips
import SwiftUI

/// A horizontal, snapping shelf of tips with names under it, standing on a ledge (docs/VISUAL.md
/// 5): tip-l at a pitch of 88 pt (104 on a regular width), the next one peeking 24 pt.
struct Rack: View {
    struct Item: Identifiable {
        var id: Int
        var name: String
        var recipe: TipRecipe
    }

    let items: [Item]
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    private let gap: CGFloat = 6

    var body: some View {
        let regular = horizontalSizeClass == .regular
        let pitch: CGFloat = regular ? 104 : 88
        let tipHeight = TipSize.l.dimensions(regular: regular).height
        ZStack(alignment: .top) {
            Ledge()
                .padding(.top, tipHeight + gap)
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(alignment: .top, spacing: 0) {
                    ForEach(items) { item in
                        VStack(spacing: 0) {
                            TipView(item.recipe, size: .l, painting: .direct)
                            Text(item.name)
                                .font(.footnote.weight(.semibold))
                                .multilineTextAlignment(.center)
                                .lineLimit(2)
                                .foregroundStyle(Color.ink)
                                .padding(.top, gap + 1.5 + 10)
                        }
                        .frame(width: pitch)
                    }
                }
                .scrollTargetLayout()
                .padding(.horizontal, 16)
            }
            .scrollTargetBehavior(.viewAligned)
        }
    }
}
