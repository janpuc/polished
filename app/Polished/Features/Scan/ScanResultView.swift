import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// What the lookup found, one block for each outcome (docs/NATIVE.md 5.3, the web's
/// `_lookup_result.html`).
struct ScanResultView: View {
    let scan: ScanModel
    let purpose: ScanPurpose
    /// Closes the scan screen.
    let close: () -> Void
    @Environment(AppModel.self) private var app
    @State private var bottleSheet: BottleSheetMode?
    @State private var confirmsForget: ScanFound?

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .animation(.smooth(duration: 0.25), value: scan.phase)
            .sheet(item: $bottleSheet) { mode in
                BottleSheet(mode: mode) {
                    app.writes.show("Added \(mode.shade.title)")
                    close()
                }
            }
            .confirmationDialog(
                "Forget that \(confirmsForget?.code ?? "") is \(confirmsForget?.shade.title ?? "")?",
                isPresented: Binding(get: { confirmsForget != nil }, set: { if !$0 { confirmsForget = nil } }),
                titleVisibility: .visible, presenting: confirmsForget
            ) { found in
                Button("Forget it", role: .destructive) { Task { await scan.forget(found) } }
            }
    }

    @ViewBuilder
    private var content: some View {
        switch scan.phase {
        case .idle:
            EmptyView()
        case .looking:
            ProgressView()
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
                .accessibilityLabel("Looking")
        case .match(let found):
            matchCard(found)
        case .suggestion(let found):
            suggestionCard(found)
        case .unknownCode(let code):
            unknown(
                lead: "New barcode \(code). Which shade is it?", lede: "Pick it once and the next scan finds it.",
                id: "scan-unknown-code")
        case .unknownPrinted(let code):
            unknown(
                lead: "\(code) isn\u{2019}t on any bottle yet. Which shade is it?",
                lede: "Pick the shade and the P code goes on the bottle you add.", id: "scan-unknown-printed")
        case .invalid(let text, let scanned):
            invalid(text: text, scanned: scanned)
        case .results(let query, let results):
            resultsList(query: query, results)
        case .failed(let message):
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Color.bad)
                .accessibilityIdentifier("scan-failed")
        }
    }

    // MARK: Outcomes

    private func matchCard(_ found: ScanFound) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let notice = found.notice {
                Text(notice)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.ink)
                    .accessibilityIdentifier("scan-notice")
            }
            Text(found.lead)
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
                .accessibilityIdentifier("scan-lead")
            ShadeCard(shade: found.shade, opensShade: !purpose.isLayer, close: close)
            HStack(spacing: 12) {
                addButton(found.shade, printedCode: found.printedCode, title: purpose.actionTitle)
                if found.identifierID != nil {
                    Button("This isn\u{2019}t it") { confirmsForget = found }
                        .buttonStyle(SecondaryButtonStyle())
                        .accessibilityIdentifier("scan-not-it")
                }
            }
            GeneralError(message: scan.learnError)
        }
    }

    private func suggestionCard(_ found: ScanFound) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Is it \(found.shade.title)?")
                .font(.title3.weight(.semibold))
                .foregroundStyle(Color.ink)
                .accessibilityIdentifier("scan-suggestion")
            Text("\(found.code) was \(found.shade.title) on a bottle you added before. A P code can differ between batches, so check the bottle.")
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
                .fixedSize(horizontal: false, vertical: true)
            ShadeCard(shade: found.shade, opensShade: !purpose.isLayer, close: close)
            addButton(
                found.shade, printedCode: found.printedCode,
                title: purpose.isLayer ? "Yes, add a layer" : "Yes, add a bottle")
            SectionHeading(title: "Not that one? Pick the shade")
                .padding(.top, 8)
            LearnPicker(scan: scan)
        }
    }

    private func unknown(lead: String, lede: String, id: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(lead)
                .font(.title3.weight(.semibold))
                .foregroundStyle(Color.ink)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier(id)
            Text(lede)
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
            LearnPicker(scan: scan)
        }
    }

    @ViewBuilder
    private func invalid(text: String, scanned: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if scanned {
                Text("Couldn\u{2019}t read that reliably. Try again.")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.bad)
            } else {
                Text("\u{201C}\(text)\u{201D} isn\u{2019}t a valid barcode number.")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.bad)
                Text("Barcodes on bottles have 12 or 13 digits (8 on small ones) and the last digit is a check digit, so one wrong digit is caught. Check the digits against the bottle.")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("scan-invalid")
    }

    @ViewBuilder
    private func resultsList(query: String, _ results: LookupResults) -> some View {
        if results.items.isEmpty {
            Text("Nothing matches \u{201C}\(query)\u{201D}. Try fewer letters.")
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
                .accessibilityIdentifier("scan-no-results")
        } else {
            VStack(alignment: .leading, spacing: 8) {
                Text(results.total == 1 ? "1 shade" : "\(results.total) shades")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                VStack(spacing: 0) {
                    ForEach(Array(results.items.enumerated()), id: \.element.id) { index, shade in
                        Button {
                            choose(shade)
                        } label: {
                            ShadeChoiceRow(shade: shade, trailing: purpose.isLayer ? "plus" : "chevron.right")
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("scan-result-\(shade.id)")
                        if index < results.items.count - 1 { Divider().padding(.leading, 64) }
                    }
                }
                .groupCard()
            }
            .accessibilityIdentifier("scan-results")
        }
    }

    // MARK: Actions

    private func addButton(_ shade: ShadeRow, printedCode: String?, title: String) -> some View {
        Button {
            switch purpose {
            case .bottle:
                bottleSheet = .add(shade, printedCode: printedCode)
            case .layer(let pick):
                pick(shade)
                close()
            }
        } label: {
            Text(title)
        }
        .buttonStyle(PrimaryButtonStyle())
        .accessibilityIdentifier("scan-add")
    }

    /// A shade picked from a name search: its page, or a layer of the swatch.
    private func choose(_ shade: ShadeRow) {
        switch purpose {
        case .bottle:
            close()
            app.router.open(.shade(id: shade.id))
        case .layer(let pick):
            pick(shade)
            close()
        }
    }
}

/// The shade a code means: the shop's bottle photo (when the catalog has one) next to the app's own
/// painted tip, then the name, the finishes and the price. Opens the shade.
private struct ShadeCard: View {
    let shade: ShadeRow
    let opensShade: Bool
    let close: () -> Void
    @Environment(AppModel.self) private var app

    var body: some View {
        Button {
            guard opensShade else { return }
            close()
            app.router.open(.shade(id: shade.id))
        } label: {
            HStack(spacing: 14) {
                if let photo = shade.heroImageUrl {
                    ShopPhoto(url: photo, width: 216, height: 288)
                        .frame(width: 72, height: 96)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .accessibilityLabel("\(shade.title), bottle photo")
                }
                TipView(shade.recipe, size: .l)
                    .padding(.vertical, 8)
                VStack(alignment: .leading, spacing: 4) {
                    Text(shade.title)
                        .font(.headline)
                        .foregroundStyle(Color.ink)
                        .multilineTextAlignment(.leading)
                    if !shade.finishLine.isEmpty {
                        Text(shade.finishLine)
                            .font(.subheadline)
                            .foregroundStyle(Color.ink2)
                            .multilineTextAlignment(.leading)
                    }
                    if let price = shade.priceCents {
                        Text(Words.money(price))
                            .font(.subheadline)
                            .monospacedDigit()
                            .foregroundStyle(Color.ink2)
                    }
                }
                Spacer(minLength: 0)
                if opensShade {
                    Image(systemName: "chevron.right")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Color.ink3)
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .groupCard()
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(shade.spokenLabel)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("scan-shade-card")
    }
}

/// A shade as a choice: the small tip, the name, the finishes.
struct ShadeChoiceRow: View {
    let shade: ShadeRow
    var trailing = "chevron.right"

    var body: some View {
        HStack(spacing: 12) {
            TipView(shade.recipe, size: .s)
                .padding(.vertical, 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(shade.title)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                if !shade.finishLine.isEmpty {
                    Text(shade.finishLine)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink2)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            Image(systemName: trailing)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Color.ink3)
        }
        .padding(.horizontal, 12)
        .frame(minHeight: 60)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(shade.spokenLabel)
        .accessibilityAddTraits(.isButton)
    }
}

/// Teaches the code on screen a shade: search the catalog by name, tap the one it is.
struct LearnPicker: View {
    let scan: ScanModel
    @Environment(AppModel.self) private var app
    @State private var query = ""
    @State private var results: [ShadeRow] = []
    @State private var searched = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(Color.ink3)
                    .accessibilityHidden(true)
                TextField("Search shades by name\u{2026}", text: $query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .accessibilityIdentifier("learn-field")
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 48)
            .background(Color.fill, in: Capsule())

            if scan.isLearning {
                ProgressView().frame(maxWidth: .infinity)
            }
            GeneralError(message: scan.learnError)
            if !results.isEmpty {
                VStack(spacing: 0) {
                    ForEach(Array(results.prefix(8).enumerated()), id: \.element.id) { index, shade in
                        Button {
                            Task { await scan.learn(shade) }
                        } label: {
                            ShadeChoiceRow(shade: shade)
                        }
                        .buttonStyle(.plain)
                        .disabled(scan.isLearning)
                        .accessibilityIdentifier("learn-row-\(shade.id)")
                        if index < min(results.count, 8) - 1 { Divider().padding(.leading, 64) }
                    }
                }
                .groupCard()
            } else if searched, !query.trimmingCharacters(in: .whitespaces).isEmpty {
                Text("Nothing matches \u{201C}\(query)\u{201D}.")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
            }
        }
        .task(id: query) {
            let words = query.trimmingCharacters(in: .whitespaces)
            guard !words.isEmpty else {
                results = []
                searched = false
                return
            }
            try? await Task.sleep(for: .milliseconds(200))
            guard !Task.isCancelled else { return }
            var search = ShadeQuery()
            search.q = words
            if let page = try? await app.api.shades(search) {
                results = page.items
                searched = true
            }
        }
    }
}
