import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// What closing the builder did to the slot, for the wheel behind it.
enum BuilderOutcome {
    /// Closed without discarding: the draft stays and the slot shows it.
    case closed
    case saved(SlotResult)
    case cancelled
    case removed
}

/// The slot the builder is open on. The model lives as long as the presentation does.
struct BuilderTarget: Identifiable {
    let position: Int
    /// The slot holds a saved swatch (so it can be removed).
    let saved: Bool
    let model: BuilderModel

    var id: Int { position }
}

/// The layer builder (docs/NATIVE.md 5.2, 5.3; docs/DESIGN.md 10): the composite tip beside the
/// slot, the layers in painting order with their coats, the templates, the picker, and a
/// disclosure for the name, the note and the day. Save swatch and Cancel are the bar's.
struct BuilderView: View {
    let target: BuilderTarget
    let wheelName: String
    let onFinish: (BuilderOutcome) -> Void

    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var save = SaveAction()
    @State private var name = ""
    @State private var note = ""
    @State private var paintedOn: String?
    @State private var showsDetails = false
    @State private var showsCopySources = false
    @State private var confirmsRemoval = false
    @State private var loadedFields = false
    @State private var showsScan = false
    @FocusState private var searchFocused: Bool

    private var model: BuilderModel { target.model }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // The head stays put: the composite and the summary answer every tap, wherever the
                // list below has been scrolled to, and a refusal is said where it is seen.
                if horizontalSizeClass == .regular { inspectorBar }
                if let sheet = model.sheet {
                    VStack(alignment: .leading, spacing: 10) {
                        head(sheet)
                        notice
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 12)
                    Divider()
                }
                ScrollViewReader { scroll in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 22) {
                            if model.sheet != nil {
                                layersSection
                                templates
                                picker(scroll)
                                details
                                if target.saved { removeSwatch }
                            } else if let failure = model.openError {
                                LoadFailure(error: failure) { Task { await model.open() } }
                            } else {
                                ProgressView().frame(maxWidth: .infinity).padding(.top, 80)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                        .padding(.bottom, 28)
                    }
                    .scrollDismissesKeyboard(.interactively)
                }
            }
            .background(Color.board)
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { if horizontalSizeClass != .regular { bar } }
            .confirmationDialog(
                "Remove the swatch from slot \(target.position)?", isPresented: $confirmsRemoval, titleVisibility: .visible
            ) {
                Button("Remove swatch", role: .destructive) { Task { await remove() } }
            } message: {
                Text("The layers and the note go with it.")
            }
            .sheet(isPresented: $showsCopySources) {
                CopySourcesSheet(model: model, replaces: !model.layers.isEmpty) { source in
                    model.copy(from: source)
                }
            }
        }
        .task { await model.open() }
        .onChange(of: model.sheet?.stackId, initial: true) { loadFields() }
        .onChange(of: save.error) { openDetailsForErrors() }
        .sensoryFeedback(.impact(weight: .light), trigger: model.edits)
        .sensoryFeedback(.error, trigger: model.failures)
        .sensoryFeedback(.warning, trigger: model.warnings)
        .sensoryFeedback(.error, trigger: save.error)
        .interactiveDismissDisabled(save.isRunning)
    }

    // MARK: Bar

    @ToolbarContentBuilder
    private var bar: some ToolbarContent {
        ToolbarItem(placement: .cancellationAction) { cancelButton }
        ToolbarItem(placement: .confirmationAction) { saveButton }
    }

    /// An inspector has no navigation bar to hold them, so its actions sit in the pane: Close keeps
    /// the draft (there is no grabber to drag away), Cancel throws it away.
    private var inspectorBar: some View {
        HStack(spacing: 8) {
            Button {
                onFinish(.closed)
            } label: {
                Image(systemName: "xmark")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.ink)
                    .frame(width: 40, height: 40)
                    .background(Color.fill, in: Circle())
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Close")
            .accessibilityHint("Keeps this draft")
            .accessibilityIdentifier("builder-close")
            Spacer(minLength: 0)
            cancelButton.buttonStyle(CompactButtonStyle())
            saveButton.buttonStyle(CompactPrimaryButtonStyle())
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }

    private var cancelButton: some View {
        Button("Cancel") { Task { await cancel() } }
            .disabled(save.isRunning || model.sheet == nil)
            .accessibilityIdentifier("builder-cancel")
            .accessibilityHint("Throws this draft away")
    }

    private var saveButton: some View {
        Button {
            Task { await saveSwatch() }
        } label: {
            if save.showsProgress { ProgressView() } else { Text("Save swatch") }
        }
        .disabled(!model.canSave || save.isRunning)
        .accessibilityIdentifier("builder-save")
    }

    // MARK: Head

    private func head(_ sheet: StackSheet) -> some View {
        let recipe = sheet.tip.isEmpty ? nil : TipRecipe(tips: sheet.tip)
        return HStack(alignment: .center, spacing: 18) {
            ZStack {
                // The composite is drawn again from the layers' recipes on every change and fades
                // from the old one (docs/NATIVE.md 5.2).
                TipView(recipe, size: .l, painting: .direct)
                    .id(recipe)
                    .transition(.opacity)
            }
            .animation(.smooth(duration: reduceMotion ? 0.15 : 0.3), value: recipe)
            .padding(.vertical, 6)
            VStack(alignment: .leading, spacing: 3) {
                Text("Slot \(target.position)")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(Color.ink)
                    .accessibilityAddTraits(.isHeader)
                Text(wheelName)
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                if model.resumed {
                    Text("Resumed your draft.")
                        .font(.footnote)
                        .foregroundStyle(Color.ink2)
                        .accessibilityIdentifier("builder-resumed")
                }
                Text(sheet.summary.isEmpty ? "Nothing painted yet" : sheet.summary)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(sheet.summary.isEmpty ? Color.ink3 : Color.ink)
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)
                    .contentTransition(.opacity)
                    .animation(.smooth(duration: 0.2), value: sheet.summary)
                    .accessibilityIdentifier("builder-summary")
            }
            Spacer(minLength: 0)
        }
    }

    @ViewBuilder
    private var notice: some View {
        if let message = model.notice ?? save.generalError {
            Button {
                model.clearNotice()
                save.clearError()
            } label: {
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(Color.ink)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color.fill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("builder-notice")
            .transition(.opacity)
        }
    }

    // MARK: Layers

    private var layersSection: some View {
        let layers = model.layers
        return VStack(alignment: .leading, spacing: 10) {
            if layers.isEmpty {
                Text("Add the base first, or start from a template.")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                    .padding(.vertical, 6)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(layers.enumerated()), id: \.element.id) { index, layer in
                        LayerRow(
                            layer: layer, isFirst: index == 0, isLast: index == layers.count - 1, model: model
                        )
                        .transition(
                            reduceMotion
                                ? .opacity : .scale(scale: 0.94, anchor: .top).combined(with: .opacity))
                    }
                }
                .groupCard()
                .accessibilityIdentifier("builder-layers")
            }
        }
        .animation(reduceMotion ? .easeOut(duration: 0.15) : .smooth(duration: 0.3), value: layers.map(\.id))
    }

    // MARK: Templates

    private var templates: some View {
        FlowLayout(spacing: 8, lineSpacing: 0) {
            Button("Over black") { model.overBlack() }
                .accessibilityIdentifier("template-over-black")
            Button("Copy from…") { showsCopySources = true }
                .accessibilityIdentifier("template-copy")
            Button("Same as last") { model.sameAsLast() }
                .accessibilityIdentifier("template-last")
        }
        .buttonStyle(CompactButtonStyle())
        .disabled(model.sheet == nil)
    }

    // MARK: Picker

    private struct PickKey: Hashable {
        var query: String
        var scope: PickScope
    }

    private func picker(_ scroll: ScrollViewProxy) -> some View {
        @Bindable var model = model
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(Color.ink3)
                    .accessibilityHidden(true)
                TextField("Search shades or a P code", text: $model.query)
                    .focused($searchFocused)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .accessibilityIdentifier("builder-search")
                if !model.query.isEmpty {
                    Button {
                        model.query = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Color.ink3)
                            .frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .accessibilityLabel("Clear search")
                }
            }
            .padding(.leading, 14)
            .padding(.trailing, model.query.isEmpty ? 14 : 0)
            .frame(minHeight: 44)
            .background(Color.fill, in: Capsule())
            .id("picker")
            .onChange(of: searchFocused) {
                if searchFocused {
                    withAnimation(.smooth) { scroll.scrollTo("picker", anchor: .top) }
                }
            }
                ScanButton { showsScan = true }
            }
            .scanCover(isPresented: $showsScan, purpose: .layer { shade in model.add(shade) })

            Picker("Show", selection: $model.scope) {
                ForEach(PickScope.allCases) { scope in Text(scope.title).tag(scope) }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("builder-scope")
            .sensoryFeedback(.selection, trigger: model.scope)

            results
        }
        .task(id: PickKey(query: model.query, scope: model.scope)) {
            if !model.query.isEmpty { try? await Task.sleep(for: .milliseconds(200)) }
            guard !Task.isCancelled else { return }
            await model.refreshPicker()
        }
    }

    @ViewBuilder
    private var results: some View {
        let query = model.query.trimmingCharacters(in: .whitespaces)
        if let pick = model.pick {
            VStack(alignment: .leading, spacing: 0) {
                if let found = pick.suggestion {
                    Text(suggestionLead(query))
                        .font(.footnote)
                        .foregroundStyle(Color.ink2)
                        .padding(.bottom, 6)
                    PickRow(shade: found, model: model, marks: false)
                        .groupCard()
                } else if pick.items.isEmpty {
                    emptyResults(query)
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(pick.items.enumerated()), id: \.element.id) { index, shade in
                            PickRow(shade: shade, model: model, marks: !query.isEmpty)
                            if index < pick.items.count - 1 { Divider().padding(.leading, 58) }
                        }
                    }
                    .groupCard()
                    if pick.total > pick.items.count {
                        Text("Showing \(pick.items.count) of \(pick.total). Type more of the name.")
                            .font(.footnote)
                            .foregroundStyle(Color.ink2)
                            .padding(.top, 8)
                    }
                }
            }
            .accessibilityIdentifier("builder-results")
        } else if model.pickFailed {
            Text("Couldn\u{2019}t load the shades. Check the connection.")
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
        } else {
            ProgressView().frame(maxWidth: .infinity).padding(.vertical, 24)
        }
    }

    private func suggestionLead(_ query: String) -> String {
        if let printed = Identifiers.normalisePrinted(query) { return "\(printed) was this on a bottle you added before:" }
        return "That code is:"
    }

    @ViewBuilder
    private func emptyResults(_ query: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if !query.isEmpty {
                let among = model.scope == .owned ? "owned " : model.scope == .toppers ? "among the toppers " : ""
                Text("Nothing \(among)matches \u{201C}\(query)\u{201D}.")
            } else if model.scope == .toppers {
                Text("No toppers in the catalog yet.")
            } else {
                Text("You don\u{2019}t own any shades yet.")
            }
            if model.scope != .all {
                Button("Search all shades") { model.scope = .all }
                    .buttonStyle(CompactButtonStyle())
            }
        }
        .font(.subheadline)
        .foregroundStyle(Color.ink2)
    }

    // MARK: Name, note, day

    private var details: some View {
        DisclosureGroup(isExpanded: $showsDetails) {
            VStack(alignment: .leading, spacing: 14) {
                TextField("Name, for example Midnight jelly", text: $name)
                    .accessibilityIdentifier("builder-name")
                    .onChange(of: name) { name = String(name.prefix(80)) }
                    .frame(minHeight: 44)
                Divider()
                TextField("Note", text: $note, axis: .vertical)
                    .lineLimit(2...5)
                    .accessibilityIdentifier("builder-note")
                    .onChange(of: note) { note = String(note.prefix(500)) }
                    .frame(minHeight: 44, alignment: .top)
                Divider()
                DateField(title: "Painted on", iso: $paintedOn, error: save.fieldErrors["painted_on"])
            }
            .padding(.top, 8)
        } label: {
            Text("Name and note").foregroundStyle(Color.ink)
        }
        .tint(Color.ink2)
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .groupCard()
        .accessibilityIdentifier("builder-details")
    }

    private var removeSwatch: some View {
        Button("Remove swatch", role: .destructive) { confirmsRemoval = true }
            .frame(maxWidth: .infinity, minHeight: 44)
            .disabled(save.isRunning)
            .accessibilityIdentifier("remove-swatch")
    }

    // MARK: Actions

    private func loadFields() {
        guard let sheet = model.sheet, !loadedFields else { return }
        loadedFields = true
        name = sheet.name ?? ""
        note = sheet.note ?? ""
        paintedOn = sheet.paintedOn ?? app.day.today()
        showsDetails = !name.isEmpty || !note.isEmpty
    }

    private func openDetailsForErrors() {
        if save.fieldErrors["painted_on"] != nil { showsDetails = true }
    }

    private func saveSwatch() async {
        searchFocused = false
        let trimmedName = name.trimmingCharacters(in: .whitespaces)
        let trimmedNote = note.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let result = await save.run({ try await model.save(name: trimmedName, note: trimmedNote, paintedOn: paintedOn) })
        else { return }
        onFinish(.saved(result))
    }

    private func cancel() async {
        searchFocused = false
        if await save.run({ try await model.cancel() }) != nil {
            onFinish(.cancelled)
            return
        }
        // A draft that is gone already has nothing left to cancel.
        switch save.error {
        case .notFound?, .conflict?: onFinish(.cancelled)
        default: break
        }
    }

    private func remove() async {
        guard await save.run({ try await model.clearSlot() }) != nil else { return }
        onFinish(.removed)
    }
}
