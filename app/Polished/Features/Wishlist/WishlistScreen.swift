import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The wishlist: the checkout head (what is in stock and the shop's cart link), then the shades
/// by priority. Reading only until run 3.
struct WishlistTab: View {
    @Environment(AppModel.self) private var app
    @State private var wishlist = Resource<Wishlist>()
    @State private var maxPriority: Int?
    @State private var checkout: URL?
    @State private var copied = false
    @Namespace private var tips

    private let includes: [(Int?, String)] = [(1, "Want most"), (2, "Plus would like"), (nil, "Everything")]
    private let priorityLabels = [1: "Want most", 2: "Would like", 3: "Maybe one day"]

    private var endpoint: Endpoint<Wishlist> { .wishlist(maxPriority: maxPriority) }

    var body: some View {
        NavigationStack(path: Binding(get: { app.router.path(.wishlist) }, set: { app.router.setPath(.wishlist, $0) })) {
            List {
                if let value = wishlist.value {
                    if value.items.isEmpty && maxPriority == nil {
                        EmptyState(line: "Nothing wished yet. Tap the heart on a shade.")
                            .listRowBackground(Color.clear)
                            .listRowSeparator(.hidden)
                    } else {
                        Section { head(value) }
                            .listRowBackground(Color.clear)
                            .listRowInsets(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))
                            .listRowSeparator(.hidden)
                        ForEach([1, 2, 3], id: \.self) { priority in
                            let rows = value.items.filter { $0.priority == priority }
                            if !rows.isEmpty {
                                Section {
                                    ForEach(rows) { item in
                                        NavigationLink(value: Route.shade(item.shade.id)) {
                                            WishRow(item: item)
                                        }
                                        .listRowBackground(Color.surface)
                                    }
                                } header: {
                                    HStack(spacing: 6) {
                                        Text(priorityLabels[priority] ?? "").font(.headline)
                                        Text("\(rows.count)").font(.subheadline).foregroundStyle(Color.ink2)
                                    }
                                    .foregroundStyle(Color.ink)
                                    .textCase(nil)
                                    .accessibilityElement(children: .combine)
                                    .accessibilityAddTraits(.isHeader)
                                }
                            }
                        }
                    }
                } else if let error = wishlist.error {
                    LoadFailure(error: error) { Task { await wishlist.load(endpoint, api: app.api) } }
                        .listRowBackground(Color.clear)
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Wishlist")
            .routeDestinations()
            .revalidating(wishlist, endpoint)
            .safariSheet($checkout)
        }
        .environment(\.tipNamespace, tips)
    }

    private func head(_ value: Wishlist) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if let cart = URL(string: value.cart.url ?? "") {
                VStack(alignment: .leading, spacing: 2) {
                    (Text(Words.money(value.cart.totalCents)).fontWeight(.bold).monospacedDigit()
                        + Text(" for \(value.cart.count) shade\(value.cart.count == 1 ? "" : "s") in stock"))
                        .font(.headline)
                        .foregroundStyle(Color.ink)
                    if value.cart.skipped > 0 {
                        Text("\(value.cart.skipped) not buyable")
                            .font(.footnote)
                            .foregroundStyle(Color.ink2)
                    }
                }
                Button("Open in Holo Taco checkout") { checkout = cart }
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("checkout-button")
                Button {
                    copyList(value.cart.names)
                } label: {
                    Label(copied ? "Copied" : "Copy list", systemImage: copied ? "checkmark" : "doc.on.doc")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Color.ink)
                        .frame(minHeight: 44)
                }
            } else {
                Text("Nothing on this part of the list is in stock right now")
                    .font(.headline)
                    .foregroundStyle(Color.ink)
            }
            Picker("Include in the checkout", selection: $maxPriority) {
                ForEach(includes, id: \.1) { Text($0.1).tag($0.0) }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("wishlist-include")
        }
        .padding(16)
        .groupCard()
    }

    private func copyList(_ names: [String]) {
        UIPasteboard.general.string = names.joined(separator: "\n")
        copied = true
        Task {
            try? await Task.sleep(for: .seconds(2))
            copied = false
        }
    }
}

private struct WishRow: View {
    let item: WishlistItem

    var body: some View {
        HStack(spacing: 14) {
            TipView(item.shade.recipe, size: .m)
                .tipSource(item.shade.id)
                .padding(.vertical, 6)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline) {
                    Text(item.shade.title)
                        .font(.headline)
                        .foregroundStyle(Color.ink)
                        .lineLimit(2)
                    Spacer(minLength: 8)
                    if let cents = item.shade.priceCents {
                        Text(Words.money(cents))
                            .font(.subheadline)
                            .monospacedDigit()
                            .foregroundStyle(Color.ink2)
                    }
                }
                HStack(spacing: 6) {
                    if let word = item.shade.statusWord {
                        Text(word).foregroundStyle(item.shade.status == nil ? Color.ink3 : item.shade.statusColor)
                    }
                    if item.shade.ownedCount > 0 {
                        Text("Owned ×\(item.shade.ownedCount)").foregroundStyle(Color.ink2)
                    }
                }
                .font(.subheadline)
                if let note = item.note {
                    Text(note)
                        .font(.footnote)
                        .foregroundStyle(Color.ink2)
                        .lineLimit(2)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(item.shade.title), " + (item.shade.priceCents.map { "\(Words.money($0)), " } ?? "")
                + (item.note ?? ""))
    }
}
