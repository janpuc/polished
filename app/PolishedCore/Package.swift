// swift-tools-version: 6.0
import PackageDescription

// The macOS platform is declared only so `swift test` can run the logic tests on the Mac;
// the app ships for iOS alone.
let package = Package(
    name: "PolishedCore",
    platforms: [.iOS("27.0"), .macOS("27.0")],
    products: [
        .library(name: "NailTips", targets: ["NailTips"]),
        .library(name: "PolishedModels", targets: ["PolishedModels"]),
        .library(name: "PolishedAPI", targets: ["PolishedAPI"]),
        .library(name: "PolishedStore", targets: ["PolishedStore"]),
    ],
    targets: [
        .target(name: "NailTips"),
        .target(name: "PolishedModels", dependencies: ["NailTips"]),
        .target(name: "PolishedAPI", dependencies: ["PolishedModels"]),
        .target(name: "PolishedStore", dependencies: ["PolishedModels"]),
        .testTarget(
            name: "PolishedCoreTests",
            dependencies: ["NailTips", "PolishedModels", "PolishedAPI", "PolishedStore"]
        ),
    ]
)
