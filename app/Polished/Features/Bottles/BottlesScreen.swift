import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

enum BottlesMode: String, CaseIterable, Identifiable {
    case collection = "Collection"
    case history = "History"

    var id: String { rawValue }
}

/// Bottles: what is on the shelf by shade, with the level in ink, and History, the buying by
/// month. A phone pushes the shade; a regular width shows it beside the list.
struct BottlesTab: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(AppModel.self) private var app
    @State private var mode = BottlesMode.collection
    @Namespace private var tips

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                BottlesSplit(mode: $mode)
            } else {
                NavigationStack(path: Binding(get: { app.router.path(.bottles) }, set: { app.router.setPath(.bottles, $0) })) {
                    BottlesListScreen(mode: $mode, selection: nil)
                        .routeDestinations()
                }
            }
        }
        .environment(\.tipNamespace, tips)
    }
}

private struct BottlesSplit: View {
    @Binding var mode: BottlesMode
    @Environment(AppModel.self) private var app
    @State private var detailPath: [Route] = []

    var body: some View {
        let selection = Binding<Route?>(
            get: { app.router.path(.bottles).first },
            set: { app.router.setPath(.bottles, $0.map { [$0] } ?? []) })
        NavigationSplitView {
            BottlesListScreen(mode: $mode, selection: selection)
                .navigationSplitViewColumnWidth(min: 340, ideal: 400, max: 440)
        } detail: {
            NavigationStack(path: $detailPath) {
                if case .shade(let id)? = selection.wrappedValue {
                    ShadeDetailScreen(id: id).id(id)
                } else {
                    SplitPlaceholder(line: "Pick a bottle")
                }
            }
            .routeDestinations()
            .onChange(of: selection.wrappedValue) { detailPath = [] }
        }
    }
}

struct BottlesListScreen: View {
    @Binding var mode: BottlesMode
    let selection: Binding<Route?>?

    var body: some View {
        Group {
            switch mode {
            case .collection: CollectionList(selection: selection)
            case .history: HistoryList(selection: selection)
            }
        }
        .scrollContentBackground(.hidden)
        .background(Color.board)
        .navigationTitle(mode.rawValue)
        .toolbarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Picker("View", selection: $mode) {
                    ForEach(BottlesMode.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 220)
                .accessibilityIdentifier("bottles-mode")
            }
        }
    }
}

// MARK: Collection

private struct CollectionList: View {
    let selection: Binding<Route?>?
    @Environment(AppModel.self) private var app
    @State private var groups = Resource<BottleGroups>()
    @State private var state: BottleState?
    @State private var archived = false
    @State private var bottleSheet: BottleSheetMode?

    private var endpoint: Endpoint<BottleGroups> { .bottles(state: state?.rawValue, archived: archived) }

    var body: some View {
        content
            .revalidating(groups, endpoint)
            .sheet(item: $bottleSheet) { BottleSheet(mode: $0) }
    }

    @ViewBuilder
    private var content: some View {
        if let selection {
            List(selection: selection) { rows }.listSectionSpacing(.compact)
        } else {
            List { rows }.listSectionSpacing(.compact)
        }
    }

    @ViewBuilder
    private var rows: some View {
        Section {
            levelChips
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 0, leading: 0, bottom: 0, trailing: 0))
            filterLine
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 0, leading: 4, bottom: 4, trailing: 4))
        }
        .listRowSeparator(.hidden)
        if let value = groups.value {
            if value.groups.isEmpty {
                emptyState
            }
            ForEach(value.groups) { group in
                Section {
                    ForEach(group.bottles) { bottle in
                        BottleRow(
                            bottle: bottle,
                            onEdit: { bottleSheet = .edit(bottle, group.shade) },
                            onLevel: { level in Task { await setLevel(bottle, to: level) } }
                        )
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.surface)
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(bottle.archived ? "Restore" : "Archive") { Task { await archive(bottle) } }
                                .tint(Color.ink2)
                        }
                    }
                } header: {
                    NavigationLink(value: Route.shade(group.shade.id)) {
                        HStack(spacing: 12) {
                            TipView(group.shade.recipe, size: .m)
                                .tipSource(group.shade.id)
                                .padding(.vertical, 4)
                            Text(group.shade.title)
                                .font(.headline)
                                .foregroundStyle(Color.ink)
                                .textCase(nil)
                            Spacer()
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(group.shade.title)
                    .accessibilityIdentifier("bottle-group-\(group.shade.id)")
                }
            }
        } else if let error = groups.error {
            LoadFailure(error: error) { Task { await groups.load(endpoint, api: app.api) } }
                .listRowBackground(Color.clear)
        } else {
            ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                .listRowBackground(Color.clear)
        }
    }

    /// The level changes in this list at once; the write follows.
    private func setLevel(_ bottle: Bottle, to level: BottleState) async {
        let groups = groups
        await app.writes.changeLevel(bottle, to: level) { id, change in
            groups.update { value in
                for group in value.groups.indices {
                    if let index = value.groups[group].bottles.firstIndex(where: { $0.id == id }) {
                        change(&value.groups[group].bottles[index])
                    }
                }
            }
        }
    }

    private func archive(_ bottle: Bottle) async {
        var patch = BottlePatch()
        patch.archived = .set(!bottle.archived)
        do {
            _ = try await app.writes.perform(.updateBottle(id: bottle.id, patch), affecting: .bottleChange)
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t \(bottle.archived ? "restore" : "archive") it. \(error.message)", kind: .failure)
        } catch {}
    }

    private var levelChips: some View {
        FlowLayout(spacing: 8, lineSpacing: 0) {
            Chip(title: "All", isOn: state == nil) { state = nil }
            ForEach(BottleState.allCases, id: \.self) { level in
                Chip(title: level.label, isOn: state == level) { state = (state == level ? nil : level) }
            }
        }
    }

    private var filterLine: some View {
        HStack {
            Text(countText)
                .font(.footnote)
                .foregroundStyle(Color.ink2)
                .accessibilityIdentifier("bottle-count")
            Spacer()
            Button(archived ? "Hide archived" : "Show archived") { archived.toggle() }
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Color.ink)
        }
    }

    private var countText: String {
        if archived { return "Archived bottles" }
        guard let value = groups.value else { return " " }
        let bottles = value.groups.reduce(0) { $0 + $1.bottles.count }
        return "\(bottles) bottle\(bottles == 1 ? "" : "s") in \(value.groups.count) shade\(value.groups.count == 1 ? "" : "s")"
    }

    private var emptyState: some View {
        let line =
            archived ? "No archived bottles. Archive one from its edit sheet."
            : state != nil ? "Nothing at this level. No bottle is marked this way right now."
            : "No bottles yet. Scan the code under a bottle or add it from its shade page."
        return EmptyState(line: line)
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
    }
}

// MARK: History

private struct HistoryList: View {
    let selection: Binding<Route?>?
    @Environment(AppModel.self) private var app
    @State private var history = Resource<History>()

    var body: some View {
        content
            .revalidating(history, .history())
    }

    @ViewBuilder
    private var content: some View {
        if let selection {
            List(selection: selection) { rows }
        } else {
            List { rows }
        }
    }

    @ViewBuilder
    private var rows: some View {
        if let value = history.value {
            if value.years.isEmpty {
                EmptyState(line: "Nothing bought yet. Bottles you add show up here by month.")
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
            ForEach(value.years) { year in
                ForEach(year.months) { month in
                    Section {
                        ForEach(month.rows) { row in
                            NavigationLink(value: Route.shade(row.shade.id)) {
                                HistoryRowView(row: row)
                            }
                            .rowSurface(.shade(row.shade.id), selection: selection)
                        }
                    } header: {
                        Text(month.label)
                            .font(.headline)
                            .foregroundStyle(Color.ink)
                            .textCase(nil)
                            .accessibilityAddTraits(.isHeader)
                    } footer: {
                        Text(footer(month.count, month.totalCents, month.unpriced))
                            .font(.footnote)
                            .foregroundStyle(Color.ink2)
                    }
                }
            }
        } else if let error = history.error {
            LoadFailure(error: error) { Task { await history.load(.history(), api: app.api) } }
                .listRowBackground(Color.clear)
        } else {
            ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                .listRowBackground(Color.clear)
        }
    }

    /// "2 bottles, $16.50, 1 without a price".
    private func footer(_ count: Int, _ cents: Int, _ unpriced: Int) -> String {
        var parts = ["\(count) bottle\(count == 1 ? "" : "s")"]
        if cents > 0 || unpriced < count { parts.append(Words.money(cents)) }
        if unpriced > 0 { parts.append("\(unpriced) without a price") }
        return parts.joined(separator: ", ")
    }
}

private struct HistoryRowView: View {
    let row: HistoryRow

    var body: some View {
        HStack(spacing: 14) {
            TipView(row.shade.recipe, size: .m)
                .tipSource(row.shade.id)
                .padding(.vertical, 6)
            VStack(alignment: .leading, spacing: 3) {
                Text(row.shade.title)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                Text(line)
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
            }
            Spacer(minLength: 8)
            if let cents = row.bottle.pricePaidCents {
                Text(Words.money(cents))
                    .font(.subheadline)
                    .monospacedDigit()
                    .foregroundStyle(Color.ink)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(row.shade.title), \(line)" + (row.bottle.pricePaidCents.map { ", \(Words.money($0))" } ?? ""))
    }

    /// The day it was bought, or "Added <day>" when there is no purchase date.
    private var line: String {
        if let bought = Words.day(row.bottle.boughtOn) { return "Bought \(bought)" }
        return "Added \(Words.day(String(row.bottle.createdAt.prefix(10))) ?? "")"
    }
}
