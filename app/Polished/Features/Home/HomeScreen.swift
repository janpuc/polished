import NailTips
import SwiftUI

/// The Home shelf as a placeholder: greeting, Wear today, the rack, the collection numbers.
struct HomeScreen: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 32) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Good evening, Georgia")
                            .displayFont(.greeting)
                            .foregroundStyle(Color.ink)
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                        Text("Monday 26 October")
                            .font(.subheadline)
                            .foregroundStyle(Color.ink2)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeading(title: "Wear today")
                        WearTodayCard(shade: .acidDrip, detail: "P12, half left")
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeading(title: "Recently added", trailing: "All 9 bottles")
                        Rack(items: SampleShade.all.map { Rack.Item(id: $0.id, name: $0.name, recipe: $0.recipe) })
                            .frame(height: 118 + 6 + 11.5 + 8 + 40)
                            .padding(.horizontal, -16)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeading(title: "Collection")
                        CollectionNumbers(bottles: 9, shades: 8, wished: 6, wishedLabel: "$87.50")
                    }
                }
                .padding(16)
                .frame(maxWidth: 1120)
                .frame(maxWidth: .infinity)
            }
            .background(Color.board)
            .scrollEdgeEffectStyle(.soft, for: .top)
            .navigationTitle("Home")
            .toolbarTitleDisplayMode(.inline)
            #if DEBUG
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink("Tip gallery") { TipGalleryScreen() }
                }
            }
            #endif
        }
    }
}

/// The Wear today hero: the shade's tip-xl on the plate (Surface in light, Velvet in dark) with
/// the one filled action.
struct WearTodayCard: View {
    let shade: SampleShade
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 20) {
                TipView(shade.recipe, size: .xl, painting: .direct)
                    .padding(.vertical, 12)
                VStack(alignment: .leading, spacing: 4) {
                    Text(shade.name)
                        .displayFont(.shadeTitle)
                        .foregroundStyle(Color.ink)
                    Text(shade.detail)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink)
                    Text(detail)
                        .font(.footnote)
                        .foregroundStyle(Color.ink2)
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 12) {
                Button("I wore this") {}
                    .buttonStyle(PrimaryButtonStyle())
                Button("Another") {}
                    .buttonStyle(.plain)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .frame(minHeight: 50)
                    .padding(.horizontal, 8)
            }
        }
        .padding(16)
        .background(Color.velvet, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .strokeBorder(Color.line, lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
    }
}

private struct CollectionNumbers: View {
    let bottles: Int
    let shades: Int
    let wished: Int
    let wishedLabel: String

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            figure(bottles, "bottles")
            figure(shades, "shades")
            figure(wished, "wished, \(wishedLabel)")
        }
        .padding(.vertical, 16)
        .groupCard()
    }

    private func figure(_ value: Int, _ label: String) -> some View {
        VStack(spacing: 2) {
            DisplayNumber(value: value, role: .collectionNumber)
                .foregroundStyle(Color.ink)
            Text(label)
                .font(.footnote)
                .foregroundStyle(Color.ink2)
        }
        .frame(maxWidth: .infinity)
    }
}
