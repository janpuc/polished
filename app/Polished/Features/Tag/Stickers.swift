import CoreNFC
import Foundation

/// Why a sticker was not written or read.
enum StickerFailure: Error, Equatable {
    /// She closed the system sheet: not worth a message.
    case cancelled
    case readOnly
    case tooSmall
    case notNDEF
    case lostConnection
    case timeout
    /// The sticker was written but what it holds now is not the link.
    case mismatch
    case other(Int)

    /// The sentence the Tag page says (docs/NATIVE.md 5.3).
    var message: String {
        switch self {
        case .cancelled: ""
        case .readOnly: "This sticker is locked. Use another one."
        case .tooSmall: "This sticker is too small. Use an NTAG213 or larger."
        case .notNDEF: "This sticker can\u{2019}t hold a link. Use an NFC sticker that works with iPhone."
        case .lostConnection: "The sticker moved. Hold it still and try again."
        case .timeout: "Nothing was written. Try again and hold still."
        case .mismatch: "The sticker was written, but it reads back as something else. Try again."
        case .other(let code): "Couldn\u{2019}t write the sticker (\(code)). Try again."
        }
    }
}

/// The NFC stickers, behind a protocol so a UI test can put a fake in its place
/// (`-nfc ok` in a Debug build).
protocol StickerService: Sendable {
    /// Core NFC can read tags on this device (an iPad cannot; neither can a simulator).
    var isAvailable: Bool { get }
    /// Writes `url` as one NDEF URI record and reads it back; throws a `StickerFailure`.
    func write(_ url: URL, wheelName: String) async throws
    /// The first URI record of a sticker, nil when it holds none.
    func read() async throws -> URL?
}

/// Core NFC (docs/NATIVE.md 5.3): connect, ask the tag's NDEF status, check capacity and that it is
/// writable, write one URI record, read it back and compare. Never locks the tag. One session at a
/// time; every callback arrives on `queue`.
final class CoreNFCStickers: NSObject, StickerService, NFCNDEFReaderSessionDelegate, @unchecked Sendable {
    private enum Job {
        case write(url: URL, wheelName: String)
        case read
    }

    private let queue = DispatchQueue(label: "com.janpuc.polished.nfc")
    private var job: Job?
    private var session: NFCNDEFReaderSession?
    private var continuation: CheckedContinuation<URL?, Error>?

    var isAvailable: Bool { NFCNDEFReaderSession.readingAvailable }

    func write(_ url: URL, wheelName: String) async throws {
        _ = try await run(.write(url: url, wheelName: wheelName))
    }

    func read() async throws -> URL? {
        try await run(.read)
    }

    private func run(_ job: Job) async throws -> URL? {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard self.continuation == nil else {
                    continuation.resume(throwing: StickerFailure.other(203))
                    return
                }
                self.job = job
                self.continuation = continuation
                let session = NFCNDEFReaderSession(delegate: self, queue: self.queue, invalidateAfterFirstRead: false)
                session.alertMessage = "Hold the top of your iPhone to the sticker"
                self.session = session
                session.begin()
            }
        }
    }

    // MARK: NFCNDEFReaderSessionDelegate

    func readerSessionDidBecomeActive(_ session: NFCNDEFReaderSession) {}

    func readerSession(_ session: NFCNDEFReaderSession, didDetectNDEFs messages: [NFCNDEFMessage]) {}

    func readerSession(_ session: NFCNDEFReaderSession, didInvalidateWithError error: Error) {
        // A session that ended by itself after a result has nothing left to report.
        finish(.failure(Self.failure(for: error)))
    }

    func readerSession(_ session: NFCNDEFReaderSession, didDetect tags: [any NFCNDEFTag]) {
        guard tags.count == 1, let tag = tags.first else {
            session.alertMessage = "One sticker at a time."
            queue.asyncAfter(deadline: .now() + 0.6) { session.restartPolling() }
            return
        }
        session.connect(to: tag) { error in
            if let error { return self.fail(session, Self.failure(for: error), "Couldn\u{2019}t connect. Try again.") }
            switch self.job {
            case .write(let url, let wheelName): self.write(url, wheelName: wheelName, to: tag, in: session)
            case .read: self.read(tag, in: session)
            case nil: session.invalidate()
            }
        }
    }

    // MARK: Steps

    private func write(_ url: URL, wheelName: String, to tag: any NFCNDEFTag, in session: NFCNDEFReaderSession) {
        tag.queryNDEFStatus { status, capacity, error in
            if let error { return self.fail(session, Self.failure(for: error), "Couldn\u{2019}t read the sticker. Try again.") }
            guard let payload = NFCNDEFPayload.wellKnownTypeURIPayload(url: url) else {
                return self.fail(session, .other(0), "Couldn\u{2019}t make the link. Try again.")
            }
            let message = NFCNDEFMessage(records: [payload])
            switch status {
            case .notSupported:
                return self.fail(session, .notNDEF, "This sticker can\u{2019}t hold a link.")
            case .readOnly:
                return self.fail(session, .readOnly, "This sticker is locked. Use another one.")
            case .readWrite:
                guard message.length <= capacity else {
                    return self.fail(session, .tooSmall, "This sticker is too small.")
                }
            @unknown default:
                return self.fail(session, .notNDEF, "This sticker can\u{2019}t hold a link.")
            }
            tag.writeNDEF(message) { error in
                if let error { return self.fail(session, Self.failure(for: error), "Couldn\u{2019}t write the sticker. Try again.") }
                tag.readNDEF { written, error in
                    let found = written?.records.lazy.compactMap { $0.wellKnownTypeURIPayload() }.first
                    guard error == nil, found?.absoluteString == url.absoluteString else {
                        return self.fail(session, .mismatch, "The sticker doesn\u{2019}t read back. Try again.")
                    }
                    session.alertMessage = "Written. Tap it with your iPhone to open \(wheelName)."
                    session.invalidate()
                    self.finish(.success(found))
                }
            }
        }
    }

    private func read(_ tag: any NFCNDEFTag, in session: NFCNDEFReaderSession) {
        tag.readNDEF { message, error in
            if let error {
                // A blank sticker answers a read with an error: that is a result, not a failure.
                if (error as? NFCReaderError)?.code == .ndefReaderSessionErrorZeroLengthMessage {
                    session.alertMessage = "Read."
                    session.invalidate()
                    return self.finish(.success(nil))
                }
                return self.fail(session, Self.failure(for: error), "Couldn\u{2019}t read the sticker. Try again.")
            }
            session.alertMessage = "Read."
            session.invalidate()
            self.finish(.success(message?.records.lazy.compactMap { $0.wellKnownTypeURIPayload() }.first))
        }
    }

    private func fail(_ session: NFCNDEFReaderSession, _ failure: StickerFailure, _ spoken: String) {
        session.invalidate(errorMessage: spoken)
        finish(.failure(failure))
    }

    private func finish(_ result: Result<URL?, StickerFailure>) {
        guard let continuation else { return }
        self.continuation = nil
        job = nil
        session = nil
        continuation.resume(with: result.mapError { $0 as Error })
    }

    static func failure(for error: Error) -> StickerFailure {
        guard let nfc = error as? NFCReaderError else { return .other((error as NSError).code) }
        switch nfc.code {
        case .readerSessionInvalidationErrorUserCanceled: return .cancelled
        case .readerSessionInvalidationErrorSessionTimeout: return .timeout
        case .readerTransceiveErrorTagConnectionLost, .readerTransceiveErrorRetryExceeded: return .lostConnection
        case .ndefReaderSessionErrorTagNotWritable: return .readOnly
        case .ndefReaderSessionErrorTagSizeTooSmall: return .tooSmall
        default: return .other(nfc.errorCode)
        }
    }
}

#if DEBUG
/// A sticker that lives in memory, for the UI flows (`-nfc ok`, `-nfc other`, `-nfc readonly`):
/// "ok" starts blank, "other" holds the link of the Toppers wheel, "readonly" refuses a write. A
/// write keeps the link, so a check after it reads it back.
final class FakeStickers: StickerService, @unchecked Sendable {
    private let lock = NSLock()
    private var held: URL?
    private let readOnly: Bool

    init(mode: String, server: URL) {
        readOnly = mode == "readonly"
        held = mode == "other" ? server.appending(path: "w/7b2vdc") : nil
    }

    var isAvailable: Bool { true }

    func write(_ url: URL, wheelName: String) async throws {
        try await Task.sleep(for: .milliseconds(700))
        if readOnly { throw StickerFailure.readOnly }
        lock.withLock { held = url }
    }

    func read() async throws -> URL? {
        try await Task.sleep(for: .milliseconds(500))
        return lock.withLock { held }
    }
}
#endif
