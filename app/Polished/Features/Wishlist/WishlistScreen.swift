import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The wishlist: the checkout head (what is in stock and the shop's cart link, Copy list, I bought
/// these), then the shades by priority, each with a menu for its priority, note and removal.
struct WishlistTab: View {
    @Environment(AppModel.self) private var app
    @State private var wishlist = Resource<Wishlist>()
    @State private var maxPriority: Int?
    @State private var checkout: URL?
    @State private var copied = false
    @State private var showsBought = false
    @State private var boughtCount = 0
    @State private var noteItem: WishlistItem?
    @State private var noteText = ""
    @Namespace private var tips

    private let includes: [(Int?, String)] = [(1, "Want most"), (2, "Plus would like"), (nil, "Everything")]
    static let priorityLabels = [1: "Want most", 2: "Would like", 3: "Maybe one day"]

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
                                            WishRow(
                                                item: item,
                                                setPriority: { priority in Task { await setPriority(item, to: priority) } },
                                                editNote: { edit(note: item) },
                                                remove: { Task { await remove(item) } })
                                        }
                                        .listRowBackground(Color.surface)
                                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                            Button("Remove", role: .destructive) { Task { await remove(item) } }
                                        }
                                    }
                                } header: {
                                    HStack(spacing: 6) {
                                        Text(Self.priorityLabels[priority] ?? "").font(.headline)
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
            .sheet(isPresented: $showsBought) {
                BoughtSheet(items: wishlist.value?.items ?? []) { count in
                    boughtCount += 1
                    app.writes.show(count == 1 ? "Added 1 bottle" : "Added \(count) bottles")
                }
            }
            .alert("Note", isPresented: Binding(get: { noteItem != nil }, set: { if !$0 { noteItem = nil } })) {
                TextField("Why you want it", text: $noteText)
                Button("Cancel", role: .cancel) {}
                Button("Save") {
                    // Read now: the alert clears `noteItem` as it closes.
                    let item = noteItem
                    let text = noteText
                    Task { await saveNote(item, text) }
                }
            } message: {
                Text(noteItem?.shade.title ?? "")
            }
            .sensoryFeedback(.success, trigger: boughtCount)
        }
        .environment(\.tipNamespace, tips)
    }

    // MARK: Writes

    /// The priority changes at once, in its new section; the write follows.
    private func setPriority(_ item: WishlistItem, to priority: Int) async {
        let before = item.priority
        guard priority != before else { return }
        let wishlist = wishlist
        let id = item.id
        let unfiltered = maxPriority == nil
        await app.writes.toggle(
            lane: "wish-item-\(id)", .updateWish(id: id, WishlistPatch(priority: .set(priority))),
            affecting: .wishlistChange,
            failure: "Couldn\u{2019}t save. Still \(Self.priorityLabels[before]?.lowercased() ?? "the same").",
            apply: { wishlist.update { value in value.items.indices.filter { value.items[$0].id == id }.forEach { value.items[$0].priority = priority } } },
            revert: { wishlist.update { value in value.items.indices.filter { value.items[$0].id == id }.forEach { value.items[$0].priority = before } } },
            onSuccess: { whole in if unfiltered { wishlist.set(whole) } })
    }

    private func edit(note item: WishlistItem) {
        noteText = item.note ?? ""
        noteItem = item
    }

    private func saveNote(_ item: WishlistItem?, _ typed: String) async {
        guard let item else { return }
        let text = typed.trimmingCharacters(in: .whitespacesAndNewlines)
        let patch = WishlistPatch(note: text.isEmpty ? .clear : .set(String(text.prefix(200))))
        do {
            _ = try await app.writes.perform(.updateWish(id: item.id, patch), affecting: .wishlistChange)
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t save the note. \(error.message)", kind: .failure)
        } catch {}
    }

    private func remove(_ item: WishlistItem) async {
        do {
            _ = try await app.writes.perform(.removeWish(id: item.id), affecting: .wishlistChange)
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t remove it. \(error.message)", kind: .failure)
        } catch {}
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
                .accessibilityIdentifier("copy-list")
            } else {
                Text("Nothing on this part of the list is in stock right now")
                    .font(.headline)
                    .foregroundStyle(Color.ink)
            }
            Button {
                showsBought = true
            } label: {
                Text("I bought these").frame(maxWidth: .infinity)
            }
            .buttonStyle(SecondaryButtonStyle())
                .accessibilityIdentifier("bought-button")
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
    let setPriority: (Int) -> Void
    let editNote: () -> Void
    let remove: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            row
            Menu {
                Picker(
                    "Priority",
                    selection: Binding(get: { item.priority }, set: setPriority)
                ) {
                    ForEach([1, 2, 3], id: \.self) { Text(WishlistTab.priorityLabels[$0] ?? "").tag($0) }
                }
                Button(item.note == nil ? "Add a note" : "Edit note", systemImage: "square.and.pencil", action: editNote)
                Button("Remove from wishlist", systemImage: "heart.slash", role: .destructive, action: remove)
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.title3)
                    .foregroundStyle(Color.ink2)
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .accessibilityLabel("Priority, note and removal for \(item.shade.title)")
            .accessibilityIdentifier("wish-menu-\(item.id)")
            .sensoryFeedback(.selection, trigger: item.priority)
        }
        .contextMenu {
            Picker("Priority", selection: Binding(get: { item.priority }, set: setPriority)) {
                ForEach([1, 2, 3], id: \.self) { Text(WishlistTab.priorityLabels[$0] ?? "").tag($0) }
            }
            Button(item.note == nil ? "Add a note" : "Edit note", systemImage: "square.and.pencil", action: editNote)
            Button("Remove from wishlist", systemImage: "heart.slash", role: .destructive, action: remove)
        }
    }

    private var row: some View {
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
