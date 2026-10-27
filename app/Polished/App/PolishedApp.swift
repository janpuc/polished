import PolishedStore
import SwiftUI

@main
struct PolishedApp: App {
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
        }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var app

    var body: some View {
        content
            .tint(Color.ink)
            .statusLine()
            // Universal links reach a SwiftUI app here (docs/NATIVE.md 2.3).
            .onOpenURL { app.router.handle($0, signedIn: app.session.isSignedIn) }
            .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                if let url = activity.webpageURL { app.router.handle(url, signedIn: app.session.isSignedIn) }
            }
            .task {
                // UI tests and simulators, which cannot tap a link: `-open <url>`.
                if let url = app.launch.openURL { app.router.handle(url, signedIn: app.session.isSignedIn) }
            }
    }

    @ViewBuilder
    private var content: some View {
        #if DEBUG
        // `-screen gallery` and `-screen parity` open a debug screen straight away (UI tests,
        // the screenshot passes).
        switch UserDefaults.standard.string(forKey: "screen") {
        case "gallery": NavigationStack { TipGalleryScreen() }
        case "parity": ParityScreen()
        default: shell
        }
        #else
        shell
        #endif
    }

    @ViewBuilder
    private var shell: some View {
        if app.session.isSignedIn {
            AppTabs()
        } else {
            SignInScreen()
        }
    }
}

/// The five tabs. `.sidebarAdaptable` turns the bar into a sidebar on iPad, where Settings sits
/// at its foot; on a phone it opens from Home's mark.
struct AppTabs: View {
    @Environment(AppModel.self) private var app
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        @Bindable var router = app.router
        TabView(selection: $router.tab) {
            Tab("Home", systemImage: "house", value: AppTab.home) { HomeScreen() }
            Tab("Shades", systemImage: "drop", value: AppTab.shades) { ShadesTab() }
            Tab("Bottles", systemImage: "flask", value: AppTab.bottles) { BottlesTab() }
            Tab("Wheels", systemImage: "circle.dotted.circle", value: AppTab.wheels) { WheelsTab() }
            Tab("Wishlist", systemImage: "heart", value: AppTab.wishlist) { WishlistTab() }
            // Only the sidebar has room for it; on a phone it opens from Home's mark.
            if horizontalSizeClass == .regular {
                Tab("Settings", systemImage: "gearshape", value: AppTab.settings) {
                    NavigationStack { SettingsScreen() }
                }
            }
        }
        .tabViewStyle(.sidebarAdaptable)
        .tabBarMinimizeBehavior(.onScrollDown)
        .tagPresentation()
        .task { await app.loadHouseholdZone() }
    }
}
