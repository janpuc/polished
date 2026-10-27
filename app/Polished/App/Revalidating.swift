import PolishedAPI
import PolishedStore
import SwiftUI

private struct RevalidatingModifier<Value: Decodable & Sendable>: ViewModifier {
    let resource: Resource<Value>
    let endpoint: Endpoint<Value>
    @Environment(AppModel.self) private var app
    @Environment(\.scenePhase) private var scenePhase

    /// What a load is for: this endpoint, as of this many writes. A write reloads every screen
    /// that is up, so lists follow what was just saved.
    private struct Load: Hashable {
        var key: String
        var revision: Int
    }

    func body(content: Content) -> some View {
        content
            .task(id: Load(key: endpoint.key, revision: app.writes.revision)) {
                await resource.load(endpoint, api: app.api)
            }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await resource.load(endpoint, api: app.api) } }
            }
            .refreshable { await resource.load(endpoint, api: app.api) }
    }
}

extension View {
    /// Loads `resource` on appear and whenever the endpoint changes or a write went through, again
    /// each time the app becomes active, and on pull to refresh.
    func revalidating<Value: Decodable & Sendable>(_ resource: Resource<Value>, _ endpoint: Endpoint<Value>) -> some View {
        modifier(RevalidatingModifier(resource: resource, endpoint: endpoint))
    }
}
