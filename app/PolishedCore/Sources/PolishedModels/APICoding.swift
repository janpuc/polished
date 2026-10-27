import Foundation

/// How the API's JSON maps to the DTOs: snake_case keys become camelCase properties and back
/// (`price_cents` is `priceCents`, `hero_image_url` is `heroImageUrl`). Every DTO decodes and
/// encodes through these, so the cache and the tests agree with `LiveAPI`.
public enum APICoding {
    public static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    public static func makeEncoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }
}
