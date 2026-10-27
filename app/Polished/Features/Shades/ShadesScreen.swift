import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// Shades: search with the matched letters washed in, the filters, and every shade as a row.
/// A phone pushes the shade onto a stack; a regular width shows the list beside the detail.
struct ShadesTab: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(AppModel.self) private var app
    @State private var model = ShadeListModel()
    @Namespace private var tips

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                ShadesSplit(model: model)
            } else {
                NavigationStack(path: Binding(get: { app.router.path(.shades) }, set: { app.router.setPath(.shades, $0) })) {
                    ShadeListScreen(model: model, selection: nil)
                        .routeDestinations()
                }
            }
        }
        .environment(\.tipNamespace, tips)
    }
}

private struct ShadesSplit: View {
    @Environment(AppModel.self) private var app
    let model: ShadeListModel
    @State private var detailPath: [Route] = []
    @State private var columns = NavigationSplitViewVisibility.automatic

    var body: some View {
        let selection = Binding<Route?>(
            get: { app.router.path(.shades).first },
            set: { app.router.setPath(.shades, $0.map { [$0] } ?? []) })
        NavigationSplitView(columnVisibility: $columns) {
            ShadeListScreen(model: model, selection: selection)
                .navigationSplitViewColumnWidth(min: 340, ideal: 400, max: 440)
        } detail: {
            NavigationStack(path: $detailPath) {
                if case .shade(let id)? = selection.wrappedValue {
                    ShadeDetailScreen(id: id).id(id)
                } else {
                    SplitPlaceholder(line: "Pick a shade")
                }
            }
            .routeDestinations()
            .onChange(of: selection.wrappedValue) { detailPath = [] }
        }
        .collapsesSidebarForBuilder($columns)
    }
}

/// What a split view's detail column shows before anything is picked.
struct SplitPlaceholder: View {
    let line: String

    var body: some View {
        VStack(spacing: 20) {
            TipView.unpainted(size: .l)
            Text(line)
                .font(.body)
                .foregroundStyle(Color.ink2)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.board)
    }
}

struct ShadeListScreen: View {
    let model: ShadeListModel
    /// Non-nil in a split view's list column: rows select instead of push.
    let selection: Binding<Route?>?
    @Environment(AppModel.self) private var app
    @State private var text = ""
    @State private var showsFilters = false
    @State private var searching = false
    @State private var showsManualShade = false
    @FocusState private var searchFocused: Bool

    var body: some View {
        list
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Shades")
            .toolbarTitleDisplayMode(searching ? .inline : .large)
            .searchable(text: $text, isPresented: $searching, prompt: "Search shades")
            .searchToolbarBehavior(.minimize)
            .autocorrectionDisabled()
            .textInputAutocapitalization(.never)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) { filterButton }
            }
            .task(id: text) {
                // The list follows the field a moment after the last key.
                if text != model.query.q {
                    try? await Task.sleep(for: .milliseconds(text.isEmpty ? 0 : 250))
                    if !Task.isCancelled { model.query.q = text }
                }
            }
            .revalidating(model.first, model.endpoint)
            .onChange(of: model.endpoint.key, initial: true) { model.syncExtra() }
            .onAppear { applyPreset() }
            .onChange(of: app.router.shadesPreset) { applyPreset() }
            .sheet(isPresented: $showsManualShade) {
                ManualShadeSheet(title: model.query.q) { id in app.router.open(.shade(id: id)) }
            }
            .popover(isPresented: $showsFilters) {
                ShadeFiltersSheet(query: Binding(get: { model.query }, set: { model.query = $0 }))
                    .presentationDetents([.medium, .large])
                    .frame(minWidth: 340, idealWidth: 380, minHeight: 420)
            }
    }

    /// Home's shortcuts and its search field send the Shades tab a query to open with.
    private func applyPreset() {
        if let preset = app.router.shadesPreset {
            model.query = preset
            text = preset.q
            app.router.shadesPreset = nil
        }
        if app.router.focusSearch {
            app.router.focusSearch = false
            searching = true
        }
    }

    private var filterButton: some View {
        Button {
            showsFilters = true
        } label: {
            Image(systemName: "line.3.horizontal.decrease")
                .overlay(alignment: .topTrailing) {
                    if model.query.filterCount > 0 {
                        Text("\(model.query.filterCount)")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(Color.primaryOn)
                            .frame(minWidth: 16, minHeight: 16)
                            .background(Color.primaryFill, in: Capsule())
                            .offset(x: 10, y: -8)
                    }
                }
        }
        .accessibilityLabel(model.query.filterCount > 0 ? "Filters, \(model.query.filterCount) on" : "Filters")
        .accessibilityIdentifier("filters-button")
    }

    @ViewBuilder
    private var list: some View {
        if let selection {
            List(selection: selection) { rows }
        } else {
            List { rows }
        }
    }

    @ViewBuilder
    private var rows: some View {
        if model.first.value == nil {
            if let error = model.first.error {
                LoadFailure(error: error) { Task { await model.first.load(model.endpoint, api: app.api) } }
                    .listRowBackground(Color.clear)
            } else {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding(.top, 80)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
        } else {
            Section {
                ForEach(model.items) { shade in
                    NavigationLink(value: Route.shade(shade.id)) {
                        ShadeRowView(shade: shade)
                    }
                    .rowSurface(.shade(shade.id), selection: selection)
                    .accessibilityIdentifier("shade-row-\(shade.id)")
                    .swipeActions(edge: .leading, allowsFullSwipe: false) { heartButton(shade).tint(Color.heart) }
                    .contextMenu { heartButton(shade) }
                }
                if model.hasMore {
                    loadMore
                }
            } header: {
                countLine
            }
            if model.items.isEmpty {
                noResults
            }
        }
    }

    // MARK: The heart

    /// Add to the wishlist, or take off it; the row flips at once.
    private func heartButton(_ shade: ShadeRow) -> some View {
        Button {
            Task { await toggleWish(shade) }
        } label: {
            Label(
                shade.wishlisted ? "Remove from wishlist" : "Add to wishlist",
                systemImage: shade.wishlisted ? "heart.slash" : "heart")
        }
        .accessibilityIdentifier("row-heart-\(shade.id)")
    }

    private func toggleWish(_ shade: ShadeRow) async {
        let model = model
        let id = shade.id
        if shade.wishlisted {
            // A row does not know its wishlist item: the write looks it up, then deletes it.
            await app.writes.toggle(
                lane: "wish-\(id)", affecting: .wishlistChange,
                failure: "Couldn\u{2019}t save. Still on your wishlist.",
                apply: { model.update(shadeID: id) { $0.wishlisted = false } },
                revert: { model.update(shadeID: id) { $0.wishlisted = true } },
                send: { api in
                    let list = try await api.wishlist()
                    guard let item = list.items.first(where: { $0.shade.id == id }) else { return NoContent() }
                    return try await api.send(.removeWish(id: item.id))
                })
        } else {
            await app.writes.toggle(
                lane: "wish-\(id)", .wish(shadeID: id), affecting: .wishlistChange,
                failure: "Couldn\u{2019}t save. Not on your wishlist.",
                apply: { model.update(shadeID: id) { $0.wishlisted = true } },
                revert: { model.update(shadeID: id) { $0.wishlisted = false } })
        }
    }

    private var countLine: some View {
        VStack(alignment: .leading, spacing: 4) {
            if model.first.isOffline { OfflineLine().padding(.horizontal, -16) }
            Text(countText)
                .font(.footnote)
                .foregroundStyle(Color.ink2)
                .textCase(nil)
                .accessibilityIdentifier("result-count")
        }
    }

    private var countText: String {
        let total = model.total
        if model.query.hasWords {
            if total == 0 { return "" }
            return model.fuzzy
                ? "\(total) match\(total == 1 ? "" : "es"), closest first"
                : "\(total) match\(total == 1 ? "" : "es")"
        }
        return "\(total) shade\(total == 1 ? "" : "s")"
    }

    private var loadMore: some View {
        Button {
            Task { await model.loadMore(api: app.api) }
        } label: {
            HStack {
                Spacer()
                if model.isLoadingMore {
                    ProgressView()
                } else {
                    Text(model.moreError == nil ? "Load more" : "Couldn't load more. Try again")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(Color.ink)
                }
                Spacer()
            }
            .frame(minHeight: 44)
        }
        .listRowBackground(Color.surface)
        .accessibilityIdentifier("load-more")
    }

    private var noResults: some View {
        VStack(spacing: 20) {
            TipView.unpainted(size: .l)
                .padding(.bottom, 4)
            Text(model.query.hasWords ? "Nothing matches \u{201C}\(model.query.q.trimmingCharacters(in: .whitespaces))\u{201D}. Try fewer letters." : "Nothing matches these filters.")
                .font(.body)
                .foregroundStyle(Color.ink2)
                .multilineTextAlignment(.center)
            if model.query.hasWords {
                Button("Add it by hand") { showsManualShade = true }
                    .buttonStyle(SecondaryButtonStyle())
                    .accessibilityIdentifier("add-by-hand")
            }
            if model.query.filterCount > 0 {
                Button("Clear filters") {
                    let q = model.query.q
                    model.query = ShadeQuery()
                    model.query.q = q
                }
                .buttonStyle(SecondaryButtonStyle())
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
        .accessibilityIdentifier("no-results")
    }
}
