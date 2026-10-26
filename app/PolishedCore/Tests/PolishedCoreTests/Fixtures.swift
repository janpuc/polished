import Foundation

/// `spec/` of the repository: in the Xcode test bundle it is a folder reference copied in at
/// build time (app/project.yml); under `swift test` it is read from the checkout.
enum Fixtures {
    private final class BundleToken {}

    static func url(_ path: String) -> URL {
        let bundled = Bundle(for: BundleToken.self).resourceURL?.appending(path: "spec/\(path)")
        if let bundled, FileManager.default.fileExists(atPath: bundled.path(percentEncoded: false)) {
            return bundled
        }
        // .../app/PolishedCore/Tests/PolishedCoreTests/Fixtures.swift -> the repository root
        var root = URL(filePath: #filePath)
        for _ in 0..<5 { root.deleteLastPathComponent() }
        return root.appending(path: "spec/\(path)")
    }

    static func data(_ path: String) throws -> Data {
        try Data(contentsOf: url(path))
    }

    static func json(_ path: String) throws -> Any {
        try JSONSerialization.jsonObject(with: data(path))
    }

    static func decode<T: Decodable>(_ type: T.Type, from path: String) throws -> T {
        try JSONDecoder().decode(type, from: data(path))
    }
}
