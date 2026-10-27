import PolishedModels
import PolishedStore
import SwiftUI

/// A shade that is not in Holo Taco's catalog, entered by hand: a name and what kind it is
/// ("Add it by hand" from a search with no results, and from Settings). The server makes it and
/// the app opens its page.
struct ManualShadeSheet: View {
    /// What was typed in the search, or nothing.
    var title = ""
    /// Called with the new shade's id once the server has made it, after the sheet closes.
    let onCreated: (Int) -> Void
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var kind = "polish"
    @State private var save = SaveAction()
    @FocusState private var focused: Bool

    private let kinds = [("polish", "Polish"), ("topper", "Topper"), ("base", "Base")]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Name", text: $name)
                        .focused($focused)
                        .submitLabel(.done)
                        .accessibilityIdentifier("shade-name")
                        .onChange(of: name) { name = String(name.prefix(100)) }
                    FieldError(message: save.fieldErrors["title"])
                } footer: {
                    Text("For a bottle that is not on holotaco.com. It gets a nail tip like any other, and you can set its colour on its page.")
                }
                .listRowBackground(Color.surface)

                Section("Kind") {
                    Picker("Kind", selection: $kind) {
                        ForEach(kinds, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityIdentifier("shade-kind")
                    FieldError(message: save.fieldErrors["kind"])
                }
                .listRowBackground(Color.surface)

                if let message = save.generalError {
                    Section { GeneralError(message: message) }
                        .listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Add a shade by hand")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                SheetBar(
                    saveTitle: "Add shade", save: save,
                    isEnabled: !name.trimmingCharacters(in: .whitespaces).isEmpty,
                    onCancel: { dismiss() }, onSave: { Task { await submit() } })
            }
            .sensoryFeedback(.error, trigger: save.error)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
        .interactiveDismissDisabled(save.isRunning)
        .onAppear {
            name = title
            focused = true
        }
    }

    private func submit() async {
        let request = ManualShadeRequest(title: name.trimmingCharacters(in: .whitespaces), kind: kind)
        guard let created = await save.run({ try await app.writes.perform(.createShade(request), affecting: .shadeChange) })
        else { return }
        dismiss()
        onCreated(created.shade.id)
    }
}
