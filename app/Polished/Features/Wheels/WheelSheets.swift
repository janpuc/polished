import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// Make a wheel: a name and how many slots it has (1 to 40). Opens the wheel once it exists.
struct NewWheelSheet: View {
    /// Called with the new wheel after the sheet closes.
    let onCreated: (Wheel) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var slots = 20
    @State private var save = SaveAction()
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Name", text: $name)
                        .focused($focused)
                        .submitLabel(.done)
                        .accessibilityIdentifier("wheel-name")
                        .onChange(of: name) { name = String(name.prefix(60)) }
                    FieldError(message: save.fieldErrors["name"])
                }
                .listRowBackground(Color.surface)

                Section {
                    Stepper(value: $slots, in: 1...40) {
                        HStack {
                            Text("Slots")
                            Spacer()
                            Text("\(slots)")
                                .monospacedDigit()
                                .foregroundStyle(Color.ink2)
                        }
                    }
                    .accessibilityValue("\(slots)")
                    .accessibilityIdentifier("slot-stepper")
                    FieldError(message: save.fieldErrors["slot_count"])
                } footer: {
                    Text("One slot for each nail tip on the wheel. You can't change it later.")
                }
                .listRowBackground(Color.surface)
                .sensoryFeedback(.selection, trigger: slots)

                if let message = save.generalError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("New wheel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                SheetBar(
                    saveTitle: "Make wheel", save: save,
                    isEnabled: !name.trimmingCharacters(in: .whitespaces).isEmpty,
                    onCancel: { dismiss() }, onSave: { Task { await submit() } })
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
        .onAppear { focused = true }
    }

    private func submit() async {
        let request = WheelRequest(name: name.trimmingCharacters(in: .whitespaces), slotCount: slots)
        guard let wheel = await save.run({ try await app.writes.perform(.createWheel(request), affecting: .wheelChange) })
        else { return }
        dismiss()
        onCreated(wheel)
    }
}

/// Rename a wheel; Archive (and Restore) is the quiet action under it (docs/advice v3 4.4).
struct RenameWheelSheet: View {
    let wheel: WheelDetail
    /// The wheel was archived or restored: the page goes back to the list or stays.
    let onArchiveChanged: (_ archived: Bool) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var save = SaveAction()
    @State private var confirmsArchive = false
    @FocusState private var focused: Bool

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Name", text: $name)
                        .focused($focused)
                        .submitLabel(.done)
                        .accessibilityIdentifier("wheel-name")
                        .onChange(of: name) { name = String(name.prefix(60)) }
                    FieldError(message: save.fieldErrors["name"])
                }
                .listRowBackground(Color.surface)

                Section {
                    if wheel.archived {
                        Button("Restore wheel") { Task { await setArchived(false) } }
                            .foregroundStyle(Color.ink)
                            .accessibilityIdentifier("restore-wheel")
                    } else {
                        Button("Archive wheel") { confirmsArchive = true }
                            .foregroundStyle(Color.ink)
                            .accessibilityIdentifier("archive-wheel")
                    }
                } footer: {
                    Text(wheel.archived ? "" : "An archived wheel moves out of the way. Its tag keeps working and you can restore it.")
                }
                .listRowBackground(Color.surface)
                .disabled(save.isRunning)

                if let message = save.generalError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Rename wheel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                SheetBar(
                    saveTitle: "Save name", save: save,
                    isEnabled: !name.trimmingCharacters(in: .whitespaces).isEmpty,
                    onCancel: { dismiss() }, onSave: { Task { await rename() } })
            }
            .confirmationDialog("Archive this wheel?", isPresented: $confirmsArchive, titleVisibility: .visible) {
                Button("Archive wheel") { Task { await setArchived(true) } }
            } message: {
                Text("Its tag keeps working and you can restore it.")
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
        .onAppear {
            name = wheel.name
            focused = true
        }
    }

    private func rename() async {
        let patch = WheelPatch(name: .set(name.trimmingCharacters(in: .whitespaces)))
        guard await save.run({ try await app.writes.perform(.updateWheel(id: wheel.id, patch), affecting: .wheelChange) }) != nil
        else { return }
        dismiss()
    }

    private func setArchived(_ archived: Bool) async {
        let patch = WheelPatch(archived: .set(archived))
        guard await save.run({ try await app.writes.perform(.updateWheel(id: wheel.id, patch), affecting: .wheelChange) }) != nil
        else { return }
        app.writes.show(archived ? "Archived \(wheel.name)" : "Restored \(wheel.name)")
        dismiss()
        onArchiveChanged(archived)
    }
}

/// Delete a wheel for good: the sheet is the confirmation (docs/advice v3 4.4). It counts what
/// goes with it and says what happens to the sticker; Delete wheel is the one filled action, red.
struct DeleteWheelSheet: View {
    let wheel: WheelDetail
    /// Called after the sheet closes, with how many swatches went.
    let onDeleted: (Int) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var save = SaveAction()

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("Delete \(wheel.name)?")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
                Text(
                    "This removes the wheel, its \(swatches) and its tag address. The sticker will stop opening anything."
                )
                .font(.body)
                .foregroundStyle(Color.ink2)
                .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 16) {
                    MiniRing(tiles: wheel.tiles, slotCount: wheel.slotCount, diameter: 72)
                    Text("\(wheel.name), \(wheel.filledCount) of \(wheel.slotCount)")
                        .font(.headline)
                        .foregroundStyle(Color.ink)
                    Spacer(minLength: 0)
                }
                .padding(14)
                .groupCard()
                .accessibilityElement(children: .combine)
                GeneralError(message: save.generalError)
                Spacer(minLength: 0)
                Button {
                    Task { await delete() }
                } label: {
                    if save.showsProgress {
                        ProgressView().tint(.white)
                    } else {
                        Text("Delete wheel")
                    }
                }
                .buttonStyle(DestructiveButtonStyle())
                .disabled(save.isRunning)
                .accessibilityIdentifier("confirm-delete-wheel")
            }
            .padding(20)
            .background(Color.board)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.disabled(save.isRunning)
                }
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
    }

    private var swatches: String {
        "\(wheel.filledCount) swatch\(wheel.filledCount == 1 ? "" : "es")"
    }

    private func delete() async {
        guard let result = await save.run({ try await app.writes.perform(.deleteWheel(id: wheel.id), affecting: .wheelChange) })
        else { return }
        dismiss()
        onDeleted(result.deletedSwatches)
    }
}

/// Take the tag of another wheel: the two wheels swap tags, so a sticker stuck on a discarded
/// wheel can open this one.
struct TakeTagSheet: View {
    let wheel: WheelDetail
    /// Called after the sheet closes with the wheel whose tag was taken.
    let onTaken: (WheelRef, Wheel) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var chosen: WheelRef?
    @State private var save = SaveAction()

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(wheel.others) { other in
                        Button {
                            chosen = other
                        } label: {
                            HStack {
                                Text(other.name).foregroundStyle(Color.ink)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.footnote.weight(.semibold))
                                    .foregroundStyle(Color.ink3)
                            }
                            .frame(minHeight: 44)
                            .contentShape(Rectangle())
                        }
                        .accessibilityIdentifier("take-from-\(other.slug)")
                    }
                } footer: {
                    Text("The two wheels swap tags. The sticker that opens \(other(named: chosen)) will open \(wheel.name), and the other way round.")
                }
                .listRowBackground(Color.surface)
                if let message = save.generalError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Take the tag of…")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.disabled(save.isRunning)
                }
            }
            .confirmationDialog(
                "Swap tags with \(chosen?.name ?? "")?",
                isPresented: Binding(get: { chosen != nil }, set: { if !$0 { chosen = nil } }),
                titleVisibility: .visible,
                presenting: chosen
            ) { other in
                // The choice is read here: the dialog clears `chosen` as it closes.
                Button("Take the tag") { Task { await take(other) } }
            } message: { _ in
                Text("The tag you tap will open the other wheel.")
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
    }

    private func other(named ref: WheelRef?) -> String { ref?.name ?? "another wheel" }

    private func take(_ other: WheelRef) async {
        guard
            let moved = await save.run({
                try await app.writes.perform(.takeTag(wheelID: wheel.id, from: other.id), affecting: .wheelChange)
            })
        else { return }
        dismiss()
        onTaken(other, moved)
    }
}
