import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The filters of the shade list: kind, status, mine, finishes, colours, collection and sort. A
/// sheet on a phone, a popover on a regular width.
struct ShadeFiltersSheet: View {
    @Binding var query: ShadeQuery
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var facets = Resource<Facets>()

    private let kinds = [("", "All"), ("polish", "Polish"), ("topper", "Toppers"), ("base", "Base coats")]
    private let statuses = [("", "Any"), ("buyable", "Buyable"), ("retired", "Retired"), ("sold_out", "Sold out")]
    private let owned = [("", "Any"), ("owned", "Owned"), ("not_owned", "Not owned"), ("wishlist", "Wishlist")]
    private let sorts = [("name", "Name"), ("released", "Release date, newest first"), ("newest", "Recently listed"), ("price", "Price, low to high")]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    segmented("Kind", kinds, $query.kind)
                    segmented("Status", statuses, $query.status)
                    segmented("Mine", owned, $query.owned)
                    if let values = facets.value {
                        chips("Finish", values.finish, $query.finish)
                        chips("Colour", values.color, $query.color)
                        menu("Collection", [("", "Any")] + values.collection.map { ($0, Words.label($0)) }, $query.collection)
                    }
                    menu("Sort by", sorts, $query.sort)
                }
                .padding(16)
            }
            .background(Color.board)
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Clear all") {
                        let words = query.q
                        query = ShadeQuery()
                        query.q = words
                    }
                    .disabled(query.filterCount == 0 && query.sort == "name")
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .task { await facets.load(.facets(), api: app.api) }
        }
    }

    private func segmented(_ title: String, _ options: [(String, String)], _ selection: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(Color.ink2)
            Picker(title, selection: selection) {
                ForEach(options, id: \.0) { Text($0.1).tag($0.0) }
            }
            .pickerStyle(.segmented)
        }
    }

    private func chips(_ title: String, _ values: [String], _ selection: Binding<[String]>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(Color.ink2)
            FlowLayout(spacing: 8, lineSpacing: 0) {
                ForEach(values, id: \.self) { value in
                    Chip(title: Words.label(value), isOn: selection.wrappedValue.contains(value)) {
                        if let index = selection.wrappedValue.firstIndex(of: value) {
                            selection.wrappedValue.remove(at: index)
                        } else {
                            selection.wrappedValue.append(value)
                        }
                    }
                }
            }
        }
    }

    private func menu(_ title: String, _ options: [(String, String)], _ selection: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(Color.ink2)
            Picker(title, selection: selection) {
                ForEach(options, id: \.0) { Text($0.1).tag($0.0) }
            }
            .pickerStyle(.menu)
            .tint(Color.ink)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}
