import Observation
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// When a sticker was last written for an address, kept on this device. Keyed by the wheel's
/// slug, because the sticker holds the address: a new tag URL starts again at "not written yet",
/// and two wheels that swap tags swap their dates.
struct TagRecords {
    private let defaults = UserDefaults.standard

    private func key(_ slug: String) -> String { "tag.written.\(slug)" }

    func written(_ slug: String) -> Date? { defaults.object(forKey: key(slug)) as? Date }

    func record(_ slug: String, at date: Date = Date()) { defaults.set(date, forKey: key(slug)) }

    func swap(_ first: String, _ second: String) {
        let one = written(first), two = written(second)
        defaults.set(two, forKey: key(first))
        defaults.set(one, forKey: key(second))
    }
}

/// What the Tag page is doing with a sticker.
@MainActor
@Observable
final class TagModel {
    enum Phase: Equatable {
        case idle
        case writing
        case written(wheelName: String)
        case writeFailed(StickerFailure)
        case checking
        case checked(StickerVerdict)
        case checkFailed(StickerFailure)
    }

    private(set) var phase = Phase.idle
    /// Raised after a write that read back right (the .success haptic).
    private(set) var writes = 0
    private(set) var lastWritten: Date?

    private let stickers: any StickerService
    private let records = TagRecords()

    init(stickers: any StickerService) {
        self.stickers = stickers
    }

    func load(slug: String) {
        lastWritten = records.written(slug)
    }

    func write(_ wheel: WheelDetail) async {
        guard phase != .writing, let url = URL(string: wheel.tagUrl) else { return }
        phase = .writing
        do {
            try await stickers.write(url, wheelName: wheel.name)
            records.record(wheel.slug)
            lastWritten = records.written(wheel.slug)
            writes += 1
            phase = .written(wheelName: wheel.name)
        } catch let failure as StickerFailure {
            phase = failure == .cancelled ? .idle : .writeFailed(failure)
        } catch {
            phase = .writeFailed(.other(0))
        }
    }

    func check(_ wheel: WheelDetail) async {
        guard phase != .checking else { return }
        phase = .checking
        do {
            let url = try await stickers.read()
            phase = .checked(
                StickerVerdict.of(url: url, wheelSlug: wheel.slug, tagURL: wheel.tagUrl, others: wheel.others))
        } catch let failure as StickerFailure {
            phase = failure == .cancelled ? .idle : .checkFailed(failure)
        } catch {
            phase = .checkFailed(.other(0))
        }
    }

    /// The address changed under the page: what was said about the old sticker no longer applies.
    func forget() {
        phase = .idle
    }
}

/// Tag and QR code (docs/NATIVE.md 5.3): the wheel's address as a QR code and as text, writing it
/// to a sticker, checking a sticker, and moving the tag. A sheet owned by the router, so a new tag
/// URL or a swap changes the page in place.
struct TagScreen: View {
    let slug: String
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var wheel = Resource<WheelDetail>()
    @State private var tag: TagModel
    @State private var confirmsNewTag = false
    @State private var showsTakeTag = false
    @State private var copied = false

    init(slug: String, stickers: any StickerService) {
        self.slug = slug
        _tag = State(initialValue: TagModel(stickers: stickers))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if wheel.isOffline { OfflineLine().padding(.horizontal, -16) }
                    if let value = wheel.value {
                        content(value)
                    } else if let error = wheel.error {
                        LoadFailure(error: error) { Task { await wheel.load(.wheel(slug: slug), api: app.api) } }
                    } else {
                        ProgressView().frame(maxWidth: .infinity).padding(.top, 120)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 32)
                .frame(maxWidth: 520)
                .frame(maxWidth: .infinity)
            }
            .background(Color.board)
            .navigationTitle("Tag and QR code")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("tag-done")
                }
            }
            .revalidating(wheel, .wheel(slug: slug))
            .onAppear { tag.load(slug: slug) }
            .onChange(of: slug) {
                tag.load(slug: slug)
                tag.forget()
            }
            .confirmationDialog("Make a new tag URL?", isPresented: $confirmsNewTag, titleVisibility: .visible) {
                Button("New tag URL", role: .destructive) { Task { await newTag() } }
            } message: {
                Text("The old sticker will stop working. Write the new address to the sticker again.")
            }
            .sheet(isPresented: $showsTakeTag) {
                if let value = wheel.value {
                    TakeTagSheet(wheel: value) { other, _ in
                        TagRecords().swap(slug, other.slug)
                        app.router.swapWheelSlugs(slug, other.slug)
                        app.writes.show("\(value.name) took the tag of \(other.name)")
                    }
                }
            }
            .sensoryFeedback(.success, trigger: tag.writes)
            .statusLine()
        }
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
    }

    // MARK: Content

    @ViewBuilder
    private func content(_ value: WheelDetail) -> some View {
        Text(app.stickers.isAvailable
            ? "A sticker on the wheel opens it here. Write the link once; move it any time."
            : "Write it from your iPhone. A sticker on the wheel opens it here.")
            .font(.body)
            .foregroundStyle(Color.ink2)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityIdentifier("tag-lede")
        QRCodeView(text: value.tagUrl)
            .frame(maxWidth: .infinity)
        address(value)
        if app.stickers.isAvailable { stickerControls(value) }
        moveTheTag(value)
    }

    private func address(_ value: WheelDetail) -> some View {
        HStack(spacing: 12) {
            Text(value.tagUrl)
                .font(.footnote.monospaced())
                .foregroundStyle(Color.ink)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier("tag-address")
            Button(copied ? "Copied" : "Copy") {
                UIPasteboard.general.string = value.tagUrl
                copied = true
                Task {
                    try? await Task.sleep(for: .seconds(2))
                    copied = false
                }
            }
            .buttonStyle(CompactButtonStyle())
            .accessibilityIdentifier("tag-copy")
            if let link = URL(string: value.tagUrl) {
                ShareLink(item: link) {
                    Image(systemName: "square.and.arrow.up")
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .foregroundStyle(Color.ink)
                .accessibilityLabel("Share the address")
                .accessibilityIdentifier("tag-share")
            }
        }
    }

    // MARK: Sticker

    private func stickerControls(_ value: WheelDetail) -> some View {
        let busy = tag.phase == .writing || tag.phase == .checking
        return VStack(alignment: .leading, spacing: 12) {
            Button {
                Task { await tag.write(value) }
            } label: {
                if tag.phase == .writing {
                    ProgressView().tint(Color.primaryOn)
                } else {
                    Text(isWriteFailure ? "Try again" : "Write to sticker")
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(busy)
            .accessibilityIdentifier("tag-write")

            Button {
                Task { await tag.check(value) }
            } label: {
                Text("Check the sticker").frame(maxWidth: .infinity)
            }
            .buttonStyle(SecondaryButtonStyle())
            .disabled(busy)
            .accessibilityIdentifier("tag-check")

            outcome
            Text(tag.lastWritten.map { "Written \($0.formatted(date: .abbreviated, time: .shortened))" } ?? "Not written yet")
                .font(.footnote)
                .foregroundStyle(tag.lastWritten == nil ? Color.ink3 : Color.ink2)
                .accessibilityIdentifier("tag-last-written")
        }
    }

    private var isWriteFailure: Bool {
        if case .writeFailed = tag.phase { true } else { false }
    }

    /// What the last write or check came to, in words.
    @ViewBuilder
    private var outcome: some View {
        switch tag.phase {
        case .idle, .writing, .checking:
            EmptyView()
        case .written(let name):
            line("Written. Tap it with your iPhone to open \(name).", systemImage: "checkmark.circle.fill", color: Color.ok)
        case .writeFailed(let failure), .checkFailed(let failure):
            line(failure.message, systemImage: "exclamationmark.triangle.fill", color: Color.bad)
        case .checked(let verdict):
            switch verdict {
            case .thisWheel:
                line("This sticker opens \(wheel.value?.name ?? "this wheel").", systemImage: "checkmark.circle.fill", color: Color.ok)
            case .otherWheel(let name):
                line("This sticker opens \(name), not this wheel. Write it again to change that.", systemImage: "arrow.triangle.swap", color: Color.warn)
            case .goneWheel:
                line("This sticker opens a wheel that is gone. Write it again.", systemImage: "arrow.triangle.swap", color: Color.warn)
            case .shade:
                line("This sticker opens a shade, not a wheel. Write it again to change that.", systemImage: "arrow.triangle.swap", color: Color.warn)
            case .notOurs(let what):
                line("This isn\u{2019}t one of ours. It opens \(what).", systemImage: "questionmark.circle.fill", color: Color.warn)
            case .blank:
                line("This sticker is empty. Write it to open this wheel.", systemImage: "questionmark.circle.fill", color: Color.warn)
            }
        }
    }

    private func line(_ text: String, systemImage: String, color: Color) -> some View {
        Label {
            Text(text).foregroundStyle(Color.ink)
        } icon: {
            Image(systemName: systemImage).foregroundStyle(color)
        }
        .font(.subheadline)
        .frame(maxWidth: .infinity, alignment: .leading)
        .fixedSize(horizontal: false, vertical: true)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("tag-outcome")
    }

    // MARK: Move the tag

    private func moveTheTag(_ value: WheelDetail) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Move the tag")
            VStack(spacing: 0) {
                moveRow("New tag URL", color: Color.bad, id: "new-tag-url") { confirmsNewTag = true }
                if !value.others.isEmpty {
                    Divider().padding(.leading, 16)
                    moveRow("Take the tag of…", id: "take-the-tag") { showsTakeTag = true }
                }
            }
            .groupCard()
            Text("A new URL makes the old sticker stop working. Taking another wheel\u{2019}s tag swaps the two, so the sticker you already have opens this one.")
                .font(.footnote)
                .foregroundStyle(Color.ink2)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func moveRow(_ title: String, color: Color = Color.ink, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).foregroundStyle(color)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.ink3)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 50)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }

    private func newTag() async {
        guard let value = wheel.value else { return }
        do {
            let renewed = try await app.writes.perform(.regenerateTag(wheelID: value.id), affecting: .wheelChange)
            app.router.replaceWheelSlug(slug, with: renewed.slug)
            app.writes.show("New tag URL. Write it to the sticker again.")
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t make a new tag URL. \(error.message)", kind: .failure)
        } catch {}
    }
}

/// Presents the Tag page for the wheel the router names.
private struct TagPresentation: ViewModifier {
    @Environment(AppModel.self) private var app

    private struct Target: Identifiable {
        var slug: String
        // One identity for any slug, so a new address updates the sheet instead of replacing it.
        var id: Int { 0 }
    }

    func body(content: Content) -> some View {
        content.sheet(
            item: Binding(
                get: { app.router.tagSlug.map(Target.init) },
                set: { if $0 == nil { app.router.tagSlug = nil } })
        ) { target in
            TagScreen(slug: target.slug, stickers: app.stickers)
        }
    }
}

extension View {
    /// The Tag and QR sheet, up whenever `Router.tagSlug` names a wheel.
    func tagPresentation() -> some View {
        modifier(TagPresentation())
    }
}
