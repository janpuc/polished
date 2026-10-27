import Observation
import PolishedAPI
import PolishedModels
import Foundation

/// The shade list for one query: page one through the snapshot-first `Resource`, further pages
/// appended after "Load more" (docs/NATIVE.md 5.2). A new query starts again at page one.
@MainActor
@Observable
public final class ShadeListModel {
    public var query = ShadeQuery()
    public let first = Resource<ShadePage>(keepsValueAcrossEndpoints: true)
    public private(set) var extra: [ShadeRow] = []
    public private(set) var nextPage = 2
    public private(set) var isLoadingMore = false
    public private(set) var moreError: APIError?
    @ObservationIgnored private var extraKey: String?

    public init() {}

    /// Page one with the pages loaded after it.
    public var items: [ShadeRow] { (first.value?.items ?? []) + extra }
    public var total: Int { first.value?.total ?? 0 }
    public var fuzzy: Bool { first.value?.fuzzy ?? false }
    public var hasMore: Bool { (extra.isEmpty ? first.value?.hasMore : lastHasMore) ?? false }
    private var lastHasMore = false

    public var endpoint: Endpoint<ShadePage> {
        var page1 = query
        page1.page = 1
        return .shades(page1)
    }

    /// Changes one shade wherever the list holds it (an optimistic heart).
    public func update(shadeID: Int, _ change: (inout ShadeRow) -> Void) {
        first.update { page in
            if let index = page.items.firstIndex(where: { $0.id == shadeID }) { change(&page.items[index]) }
        }
        if let index = extra.firstIndex(where: { $0.id == shadeID }) { change(&extra[index]) }
    }

    /// Forgets the extra pages when the query changed under them.
    public func syncExtra() {
        guard extraKey != endpoint.key else { return }
        extraKey = endpoint.key
        extra = []
        nextPage = 2
        lastHasMore = false
        moreError = nil
    }

    public func loadMore(api: any PolishedAPI) async {
        guard hasMore, !isLoadingMore else { return }
        isLoadingMore = true
        moreError = nil
        defer { isLoadingMore = false }
        var request = query
        request.page = nextPage
        do {
            let page = try await api.shades(request)
            extra += page.items
            lastHasMore = page.hasMore
            nextPage += 1
        } catch let failure as APIError {
            moreError = failure
        } catch {}
    }
}
