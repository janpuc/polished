import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// Which bottle the sheet is for.
enum BottleSheetMode: Identifiable {
    case add(ShadeRow)
    case edit(Bottle, ShadeRow)

    var id: String {
        switch self {
        case .add(let shade): "add-\(shade.id)"
        case .edit(let bottle, _): "edit-\(bottle.id)"
        }
    }

    var shade: ShadeRow {
        switch self {
        case .add(let shade), .edit(_, let shade): shade
        }
    }
}

/// Add bottle and Edit bottle: Level first, then Bought on, and the rest under More details.
/// Save awaits the server; a 422 puts its
/// message under the field it names. Archive and Delete live at the foot of an edit.
struct BottleSheet: View {
    let mode: BottleSheetMode
    /// Called after a bottle was added, with the sheet already closing.
    var onAdded: (() -> Void)?
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var state = BottleState.full
    @State private var boughtOn: String?
    @State private var price = ""
    @State private var openedOn: String?
    @State private var notes = ""
    @State private var showsMore = false
    @State private var confirmsDelete = false
    @State private var localPriceError: String?
    @State private var save = SaveAction()
    @State private var detent = PresentationDetent.large

    private var bottle: Bottle? {
        if case .edit(let bottle, _) = mode { bottle } else { nil }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    header
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 14, leading: 4, bottom: 6, trailing: 4))

                Section("Level") {
                    VStack(alignment: .leading, spacing: 6) {
                        LevelPicker(state: $state)
                        FieldError(message: save.fieldErrors["state"])
                    }
                    .listRowInsets(EdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12))
                }
                .listRowBackground(Color.surface)

                Section {
                    DateField(
                        title: "Bought on", iso: $boughtOn, clearLabel: "Don\u{2019}t know",
                        error: save.fieldErrors["bought_on"])
                }
                .listRowBackground(Color.surface)

                Section {
                    DisclosureGroup("More details", isExpanded: $showsMore) {
                        PriceField(
                            title: "Price paid", text: $price,
                            error: localPriceError ?? save.fieldErrors["price_paid_cents"])
                        DateField(
                            title: "Opened on", iso: $openedOn, clearLabel: "Not opened", emptyText: "Not opened",
                            error: save.fieldErrors["opened_on"])
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Notes").foregroundStyle(Color.ink)
                            TextField("Where it came from, how it wears", text: $notes, axis: .vertical)
                                .lineLimit(2...5)
                                .accessibilityIdentifier("notes")
                                .onChange(of: notes) { notes = String(notes.prefix(500)) }
                            FieldError(message: save.fieldErrors["notes"])
                        }
                    }
                    .foregroundStyle(Color.ink)
                }
                .listRowBackground(Color.surface)

                if let bottle {
                    Section {
                        Button(bottle.archived ? "Restore this bottle" : "Archive this bottle") {
                            Task { await archive(bottle) }
                        }
                        .foregroundStyle(Color.ink)
                        .disabled(save.isRunning)
                        .accessibilityIdentifier("archive-bottle")
                        Button("Delete this entry", role: .destructive) { confirmsDelete = true }
                            .disabled(save.isRunning)
                            .accessibilityIdentifier("delete-bottle")
                    }
                    .listRowBackground(Color.surface)
                }

                if let message = save.generalError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .scrollDismissesKeyboard(.interactively)
            .navigationTitle(bottle == nil ? "Add bottle" : "Edit bottle")
            // The shade is named in the bar too, so it is never lost under it when the form scrolls.
            .navigationSubtitle(mode.shade.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                SheetBar(
                    saveTitle: bottle == nil ? "Add bottle" : "Save changes", save: save,
                    onCancel: { dismiss() }, onSave: { Task { await submit() } })
            }
            .confirmationDialog("Delete this bottle entry?", isPresented: $confirmsDelete, titleVisibility: .visible) {
                Button("Delete this entry", role: .destructive) { Task { await delete() } }
            } message: {
                Text("Use Archive to keep it.")
            }
            .onChange(of: save.error) { openMoreDetailsForErrors() }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large], selection: $detent)
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
        .onAppear(perform: load)
    }

    private var header: some View {
        HStack(spacing: 14) {
            TipView(mode.shade.recipe, size: .m)
                .padding(.vertical, 4)
            Text(mode.shade.title)
                .font(.headline)
                .foregroundStyle(Color.ink)
                .lineLimit(2)
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Values

    private func load() {
        switch mode {
        case .add:
            boughtOn = app.day.today()
        case .edit(let bottle, _):
            state = bottle.state
            boughtOn = bottle.boughtOn
            price = bottle.pricePaidCents.map(Entry.field(cents:)) ?? ""
            openedOn = bottle.openedOn
            notes = bottle.notes ?? ""
            showsMore = !price.isEmpty || openedOn != nil || !notes.isEmpty
        }
    }

    private func openMoreDetailsForErrors() {
        let fields = save.fieldErrors.keys
        if fields.contains(where: { ["price_paid_cents", "opened_on", "notes"].contains($0) }) {
            showsMore = true
        }
    }

    /// The price in cents, nil when the field is empty; nil with `localPriceError` set when it is
    /// not an amount.
    private func cents() -> (value: Int?, valid: Bool) {
        let text = price.trimmingCharacters(in: .whitespaces)
        if text.isEmpty { return (nil, true) }
        guard let value = Entry.cents(text) else { return (nil, false) }
        return (value, true)
    }

    private var trimmedNotes: String? {
        let text = notes.trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty ? nil : text
    }

    // MARK: Writes

    private func submit() async {
        let amount = cents()
        guard amount.valid else {
            localPriceError = priceMessage
            showsMore = true
            return
        }
        localPriceError = nil
        switch mode {
        case .add(let shade):
            let request = BottleRequest(
                state: state, boughtOn: boughtOn, pricePaidCents: amount.value,
                openedOn: openedOn, notes: trimmedNotes)
            guard
                await save.run({
                    try await app.writes.perform(.addBottle(shadeID: shade.id, request), affecting: .bottleChange)
                }) != nil
            else { return }
            app.arrive(shadeID: shade.id)
            dismiss()
            onAdded?()
        case .edit(let bottle, _):
            var patch = BottlePatch()
            patch.state = .set(state)
            patch.boughtOn = Patch(boughtOn)
            patch.pricePaidCents = Patch(amount.value)
            patch.openedOn = Patch(openedOn)
            patch.notes = Patch(trimmedNotes)
            guard
                await save.run({ try await app.writes.perform(.updateBottle(id: bottle.id, patch), affecting: .bottleChange) })
                    != nil
            else { return }
            dismiss()
        }
    }

    private func archive(_ bottle: Bottle) async {
        var patch = BottlePatch()
        patch.archived = .set(!bottle.archived)
        guard
            await save.run({ try await app.writes.perform(.updateBottle(id: bottle.id, patch), affecting: .bottleChange) })
                != nil
        else { return }
        dismiss()
    }

    private func delete() async {
        guard let bottle else { return }
        guard await save.run({ try await app.writes.perform(.deleteBottle(id: bottle.id), affecting: .bottleChange) }) != nil
        else { return }
        dismiss()
    }
}
