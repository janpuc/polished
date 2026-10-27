import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// "I bought these": the wishlist as checkable rows with a price each and one date for all. One
/// call makes a full bottle of every ticked shade and takes it off the wishlist, or changes
/// nothing (docs/NATIVE.md 3, `POST /wishlist/bought`).
struct BoughtSheet: View {
    let items: [WishlistItem]
    /// Called with how many bottles were made, after the sheet closes.
    let onBought: (Int) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var boughtOn: String?
    @State private var ticked: Set<Int> = []
    @State private var prices: [Int: String] = [:]
    @State private var priceErrors: [Int: String] = [:]
    @State private var save = SaveAction()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    DateField(title: "Bought on", iso: $boughtOn, error: save.fieldErrors["bought_on"])
                } footer: {
                    Text("They move from the wishlist to your bottles.")
                }
                .listRowBackground(Color.surface)

                Section("Shades") {
                    if items.isEmpty {
                        Text("Nothing on the wishlist.").foregroundStyle(Color.ink2)
                    }
                    ForEach(items) { item in
                        row(item)
                    }
                }
                .listRowBackground(Color.surface)

                if ticked.isEmpty, !items.isEmpty {
                    Section { GeneralError(message: "Tick at least one shade.") }
                        .listRowBackground(Color.clear)
                }
                if let message = bottomError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle("I bought these")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                SheetBar(
                    saveTitle: "Add bottles", save: save, isEnabled: !ticked.isEmpty,
                    onCancel: { dismiss() }, onSave: { Task { await submit() } })
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
        .onAppear {
            boughtOn = app.day.today()
            ticked = Set(items.map(\.id))
            prices = Dictionary(uniqueKeysWithValues: items.map { ($0.id, $0.shade.priceCents.map(Entry.field(cents:)) ?? "") })
        }
    }

    /// The server's answer when it names no field the sheet shows.
    private var bottomError: String? {
        guard let error = save.error else { return nil }
        if case .validation(_, _, let fields) = error, fields.keys.contains("bought_on") { return nil }
        return error.message
    }

    private func row(_ item: WishlistItem) -> some View {
        let isOn = ticked.contains(item.id)
        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 12) {
                Button {
                    if isOn { ticked.remove(item.id) } else { ticked.insert(item.id) }
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
                            .font(.title3)
                            .foregroundStyle(isOn ? Color.ink : Color.ink3)
                        TipView(item.shade.recipe, size: .s)
                            .padding(.vertical, 6)
                        Text(item.shade.title)
                            .font(.body)
                            .foregroundStyle(Color.ink)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                        Spacer(minLength: 4)
                    }
                    .frame(minHeight: 52)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(item.shade.title)
                .accessibilityAddTraits(isOn ? [.isButton, .isSelected] : .isButton)
                .accessibilityIdentifier("bought-item-\(item.id)")
                Text("$").foregroundStyle(Color.ink2).accessibilityHidden(true)
                TextField(
                    "0.00",
                    text: Binding(get: { prices[item.id] ?? "" }, set: { prices[item.id] = $0; priceErrors[item.id] = nil })
                )
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .monospacedDigit()
                .frame(width: 72)
                .accessibilityLabel("Price paid for \(item.shade.title), in dollars")
                .accessibilityIdentifier("bought-price-\(item.id)")
            }
            FieldError(message: priceErrors[item.id])
        }
    }

    private func submit() async {
        var chosen: [BoughtItem] = []
        var errors: [Int: String] = [:]
        for item in items where ticked.contains(item.id) {
            let text = (prices[item.id] ?? "").trimmingCharacters(in: .whitespaces)
            if text.isEmpty {
                chosen.append(BoughtItem(id: item.id, priceCents: nil))
            } else if let cents = Entry.cents(text) {
                chosen.append(BoughtItem(id: item.id, priceCents: cents))
            } else {
                errors[item.id] = priceMessage
            }
        }
        priceErrors = errors
        guard errors.isEmpty, !chosen.isEmpty else { return }
        let request = BoughtRequest(items: chosen, boughtOn: boughtOn)
        guard let bought = await save.run({ try await app.writes.perform(.bought(request), affecting: .bottleChange) })
        else { return }
        dismiss()
        onBought(bought.bottles.count)
    }
}
