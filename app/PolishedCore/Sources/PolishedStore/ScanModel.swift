import Foundation
import Observation
import PolishedAPI
import PolishedModels

/// A code and the shade it means.
public struct ScanFound: Hashable, Sendable {
    public var code: String
    /// "gtin", "printed" or "sku".
    public var kind: String
    public var shade: ShadeRow
    /// The learned code's row, so "This isn't it" can forget it.
    public var identifierID: Int?
    /// "Saved. 810170284120 is now Spirit Fingers.", after a learn.
    public var notice: String?

    /// "Barcode 810170284120 is", "P259 is", "SKU … is".
    public var lead: String {
        switch kind {
        case "gtin": "Barcode \(code) is"
        case "printed": "\(code) is"
        default: "SKU \(code) is"
        }
    }

    /// A P code rides into the bottle form, so the bottle carries it.
    public var printedCode: String? { kind == "printed" ? code : nil }
}

/// What the scan screen shows: one case per outcome of the lookup (docs/DESIGN.md 7.2).
public enum ScanPhase: Hashable, Sendable {
    case idle
    case looking
    case match(ScanFound)
    case suggestion(ScanFound)
    /// A barcode nobody has taught the app yet.
    case unknownCode(String)
    /// A P code that is on no bottle yet.
    case unknownPrinted(String)
    /// `text` is what was typed; `scanned` when a camera read it.
    case invalid(text: String, scanned: Bool)
    case results(query: String, LookupResults)
    case failed(String)
}

/// The scan screen's state: a recognised barcode or typed words go to `GET /lookup`, the answer
/// becomes a phase, and a picked shade teaches the code (`POST /identifiers`). A barcode the
/// camera reads is checked here first (check digit, length), so a misread never costs a request.
@MainActor
@Observable
public final class ScanModel {
    public private(set) var phase = ScanPhase.idle
    /// Barcodes accepted from the camera (the haptic trigger).
    public private(set) var recognitions = 0
    /// A learn that failed, for the picker to say.
    public private(set) var learnError: String?
    public private(set) var isLearning = false
    /// How often the answer was one to be careful about: a code that already meant another shade,
    /// or a learned code forgotten (the .warning haptic).
    public private(set) var warnings = 0

    @ObservationIgnored private let api: any PolishedAPI
    @ObservationIgnored private let writes: WriteCoordinator
    /// Answers that arrive after a newer question was asked are dropped.
    @ObservationIgnored private var generation = 0
    @ObservationIgnored private var lastScanned: String?

    public init(api: any PolishedAPI, writes: WriteCoordinator) {
        self.api = api
        self.writes = writes
    }

    /// The code under the camera. Returns false when it was ignored: the camera reports the same
    /// bottle many times a second, and a question is already open for it.
    @discardableResult
    public func recognise(barcode raw: String) async -> Bool {
        guard let gtin = Identifiers.normaliseGTIN(raw) else {
            // A bad read: say so once; the camera keeps looking.
            if lastScanned == raw { return false }
            lastScanned = raw
            phase = .invalid(text: raw, scanned: true)
            return false
        }
        if lastScanned == gtin, phase != .idle { return false }
        lastScanned = gtin
        recognitions += 1
        await ask(q: gtin, via: "scan")
        return true
    }

    /// What was typed in the field: a code, a P code or words. Nothing typed clears the card.
    public func lookup(typed text: String) async {
        let words = text.trimmingCharacters(in: .whitespaces)
        guard !words.isEmpty else {
            reset()
            return
        }
        lastScanned = nil
        await ask(q: words, via: "typed")
    }

    public func reset() {
        generation += 1
        phase = .idle
        lastScanned = nil
        learnError = nil
    }

    private func ask(q: String, via: String) async {
        generation += 1
        let mine = generation
        phase = .looking
        learnError = nil
        do {
            let answer = try await api.get(.lookup(q: q, via: via))
            guard mine == generation else { return }
            phase = Self.phase(for: answer, asked: q, scanned: via == "scan")
        } catch is CancellationError {
            return
        } catch let error as APIError {
            guard mine == generation else { return }
            phase = .failed(error == .offline ? "You're offline. Connect and try again." : error.message)
        } catch {
            guard mine == generation else { return }
            phase = .failed("Couldn't look that up. Try again.")
        }
    }

    static func phase(for answer: Lookup, asked: String, scanned: Bool) -> ScanPhase {
        let code = answer.code ?? asked
        switch answer.outcome {
        case "match", "suggestion":
            guard let shade = answer.shade else { return .failed("Couldn't look that up. Try again.") }
            let found = ScanFound(
                code: code, kind: answer.kind ?? "gtin", shade: shade.row, identifierID: answer.identifierId, notice: nil)
            return answer.outcome == "match" ? .match(found) : .suggestion(found)
        case "unknown_code": return .unknownCode(code)
        case "unknown_printed": return .unknownPrinted(code)
        case "invalid_code": return .invalid(text: asked, scanned: scanned)
        case "results":
            guard let results = answer.results else { return .failed("Couldn't look that up. Try again.") }
            return .results(query: asked, results)
        default: return .failed("Couldn't look that up. Try again.")
        }
    }

    /// Teaches the server that the code on screen is `shade`; the card becomes that shade with the
    /// notice and Add bottle. A code that already meant another shade keeps it (docs/NATIVE.md 3).
    public func learn(_ shade: ShadeRow) async {
        guard let (kind, code) = learnable else { return }
        isLearning = true
        learnError = nil
        defer { isLearning = false }
        do {
            let saved = try await writes.perform(
                .learn(LearnRequest(kind: kind, value: code, shadeId: shade.id)), affecting: .codeChange)
            let notice =
                saved.created
                ? "Saved. \(code) is now \(saved.shade.title)."
                : "\(code) already points at \(saved.shade.title), so that stays."
            phase = .match(
                ScanFound(code: code, kind: kind, shade: saved.shade, identifierID: saved.identifier.id, notice: notice))
            if !saved.created { warnings += 1 }
        } catch let error as APIError {
            learnError = error.message
        } catch {
            learnError = "Couldn't save that. Try again."
        }
    }

    /// "This isn't it": forgets the learned code and asks again, which now says it is unknown.
    public func forget(_ found: ScanFound) async {
        guard let id = found.identifierID else { return }
        do {
            _ = try await writes.perform(.forgetCode(id: id), affecting: .codeChange)
            warnings += 1
            lastScanned = nil
            await ask(q: found.code, via: found.kind == "gtin" ? "scan" : "typed")
        } catch let error as APIError {
            learnError = error.message
        } catch {
            learnError = "Couldn't forget that. Try again."
        }
    }

    /// The kind and code a picked shade would be taught: an unknown barcode (gtin), an unknown P
    /// code or one whose suggestion was waved away (printed).
    private var learnable: (kind: String, code: String)? {
        switch phase {
        case .unknownCode(let code): ("gtin", code)
        case .unknownPrinted(let code): ("printed", code)
        case .suggestion(let found): (found.kind, found.code)
        default: nil
        }
    }
}
