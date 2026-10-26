import SwiftUI

/// A least-recently-used cache.
public struct LRUCache<Key: Hashable, Value> {
    public let capacity: Int
    private var storage: [Key: Value] = [:]
    private var order: [Key] = []  // least recently used first

    public init(capacity: Int) {
        self.capacity = capacity
    }

    public var count: Int { storage.count }

    public mutating func value(for key: Key) -> Value? {
        guard let value = storage[key] else { return nil }
        touch(key)
        return value
    }

    public mutating func insert(_ value: Value, for key: Key) {
        storage[key] = value
        touch(key)
        while order.count > capacity {
            storage[order.removeFirst()] = nil
        }
    }

    private mutating func touch(_ key: Key) {
        if let index = order.firstIndex(of: key) { order.remove(at: index) }
        order.append(key)
    }
}

/// Painted tips rendered once into images (`ImageRenderer` at 3x, 300 entries) so lists scroll
/// without redrawing hundreds of dots per row. The key is the recipe and the size; the lit
/// chrome around the image is drawn live, so the colour scheme is not part of it.
@MainActor
public final class TipImageCache {
    public static let shared = TipImageCache(capacity: 300)

    private struct Key: Hashable {
        var recipe: TipRecipe
        var width: Double
        var height: Double
    }

    private var cache: LRUCache<Key, CGImage>

    public init(capacity: Int) {
        cache = LRUCache(capacity: capacity)
    }

    public func image(for recipe: TipRecipe, size: CGSize) -> Image? {
        let key = Key(recipe: recipe, width: size.width, height: size.height)
        if let hit = cache.value(for: key) { return Image(decorative: hit, scale: 3) }
        let renderer = ImageRenderer(content: TipCanvas(ops: recipe.ops).frame(width: size.width, height: size.height))
        renderer.scale = 3
        guard let image = renderer.cgImage else { return nil }
        cache.insert(image, for: key)
        return Image(decorative: image, scale: 3)
    }
}
