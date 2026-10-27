import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The codes the app was taught: a barcode or P code and the shade it means, newest first. Swipe
/// to forget one; the next scan of it asks again.
struct LearnedCodesScreen: View {
    @Environment(AppModel.self) private var app
    @State private var codes = Resource<LearnedCodes>()

    var body: some View {
        content
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Learned codes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.visible, for: .navigationBar)
            .revalidating(codes, .identifiers())
    }

    @ViewBuilder
    private var content: some View {
        if let value = codes.value {
            if value.items.isEmpty {
                EmptyState(line: "Nothing learned yet. Scan a bottle and pick its shade once.")
                    .frame(maxHeight: .infinity)
                    .accessibilityIdentifier("learned-empty")
            } else {
                List {
                    Section {
                        ForEach(value.items) { code in
                            row(code)
                                .listRowBackground(Color.surface)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button("Forget", role: .destructive) { Task { await forget(code) } }
                                        .accessibilityIdentifier("learned-forget")
                                }
                        }
                    } footer: {
                        Text("Swipe a code to forget it.")
                    }
                }
                .accessibilityIdentifier("learned-list")
            }
        } else if let error = codes.error {
            LoadFailure(error: error) { Task { await codes.load(.identifiers(), api: app.api) } }
        } else {
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func row(_ code: Identifier) -> some View {
        HStack(spacing: 12) {
            TipView(code.shade.recipe, size: .s)
                .padding(.vertical, 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(code.shade.title)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                Text(label(code))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(Color.ink2)
                Text(usage(code))
                    .font(.footnote)
                    .foregroundStyle(Color.ink3)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: 60)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(code.shade.title), \(label(code)), \(usage(code))")
        .accessibilityIdentifier("learned-\(code.id)")
    }

    private func label(_ code: Identifier) -> String {
        switch code.kind {
        case "gtin": "Barcode \(code.value)"
        case "printed": code.value
        default: "SKU \(code.value)"
        }
    }

    private func usage(_ code: Identifier) -> String {
        let used = code.useCount == 1 ? "Used once" : "Used \(code.useCount) times"
        return code.lastUsedAt.flatMap { Words.day(String($0.prefix(10))) }.map { "\(used), last on \($0)" } ?? used
    }

    private func forget(_ code: Identifier) async {
        codes.update { $0.items.removeAll { $0.id == code.id } }
        do {
            _ = try await app.writes.perform(.forgetCode(id: code.id), affecting: .codeChange)
            app.writes.show("Forgot \(code.value)")
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t forget it. \(error.message)", kind: .failure)
            await codes.load(.identifiers(), api: app.api)
        } catch {}
    }
}
