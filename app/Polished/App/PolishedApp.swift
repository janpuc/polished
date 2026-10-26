import SwiftUI

@main
struct PolishedApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

struct RootView: View {
    var body: some View {
        #if DEBUG
        // `-screen gallery` and `-screen parity` open a debug screen straight away (UI tests,
        // the screenshot passes).
        switch UserDefaults.standard.string(forKey: "screen") {
        case "gallery": NavigationStack { TipGalleryScreen() }
        case "parity": ParityScreen()
        default: AppTabs()
        }
        #else
        AppTabs()
        #endif
    }
}

/// The five tabs. `.sidebarAdaptable` turns the bar into a sidebar on iPad.
struct AppTabs: View {
    var body: some View {
        TabView {
            Tab("Home", systemImage: "house") { HomeScreen() }
            Tab("Shades", systemImage: "diamond") { ShadesScreen() }
            Tab("Bottles", systemImage: "flask") { BottlesScreen() }
            Tab("Wheels", systemImage: "circle.dotted.circle") { WheelsScreen() }
            Tab("Wishlist", systemImage: "heart") { WishlistScreen() }
        }
        .tabViewStyle(.sidebarAdaptable)
        .tabBarMinimizeBehavior(.onScrollDown)
        .tint(Color.ink)
    }
}
