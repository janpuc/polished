import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// Who is signed in, where, which devices hold a token, and how the catalog sync is doing; sign
/// out. A sheet from Home's mark on a phone, a tab at the foot of the iPad sidebar.
struct SettingsScreen: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var me = Resource<Me>()
    @State private var devices = Resource<Devices>()
    @State private var sync = Resource<SyncStatus>()
    @State private var confirmsSignOut = false

    var body: some View {
        List {
            Section("Account") {
                row("Signed in as", me.value?.user.name ?? "")
                row("Server", app.serverURL.host(percentEncoded: false).map { host in
                    app.serverURL.port.map { "\(host):\($0)" } ?? host
                } ?? app.serverURL.absoluteString)
                if let server = me.value?.server {
                    row("Server version", server.version)
                    row("Shades in the catalog", "\(server.shadeCount)")
                }
            }
            .listRowBackground(Color.surface)

            Section("Devices") {
                if let items = devices.value?.items, items.isEmpty {
                    Text(app.usesDevToken ? "This build uses a development token." : "No devices yet.")
                        .foregroundStyle(Color.ink2)
                } else if let items = devices.value?.items {
                    ForEach(items) { device in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(device.deviceName).foregroundStyle(Color.ink)
                                if device.current {
                                    Text("This device")
                                        .font(.footnote.weight(.medium))
                                        .foregroundStyle(Color.ink2)
                                }
                            }
                            Text(lastUsed(device))
                                .font(.footnote)
                                .foregroundStyle(Color.ink2)
                        }
                        .accessibilityElement(children: .combine)
                    }
                } else if devices.error != nil {
                    Text("Couldn't load the devices.").foregroundStyle(Color.ink2)
                } else {
                    ProgressView()
                }
            }
            .listRowBackground(Color.surface)

            Section("Catalog sync") {
                if let last = sync.value?.last {
                    row("Last sync", syncLine(last))
                    row("Products seen", "\(last.productsSeen)")
                    if last.newShades > 0 { row("New shades", "\(last.newShades)") }
                    if let error = last.error { Text(error).font(.footnote).foregroundStyle(Color.bad) }
                } else if sync.value != nil {
                    Text("Not synced yet.").foregroundStyle(Color.ink2)
                } else if sync.error != nil {
                    Text("Couldn't load the sync status.").foregroundStyle(Color.ink2)
                } else {
                    ProgressView()
                }
            }
            .listRowBackground(Color.surface)

            Section {
                row("Version", "\(AppModel.version) (\(AppModel.build))")
                    .accessibilityIdentifier("version-row")
            }
            .listRowBackground(Color.surface)

            #if DEBUG
            Section("Debug") {
                NavigationLink("Tip gallery") { TipGalleryScreen() }
            }
            .listRowBackground(Color.surface)
            #endif

            Section {
                Button("Sign out", role: .destructive) { confirmsSignOut = true }
                    .accessibilityIdentifier("sign-out")
            }
            .listRowBackground(Color.surface)
        }
        .scrollContentBackground(.hidden)
        .background(Color.board)
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
        }
        .task {
            async let a: Void = me.load(.me(), api: app.api)
            async let b: Void = devices.load(.devices(), api: app.api)
            async let c: Void = sync.load(.sync(), api: app.api)
            _ = await (a, b, c)
        }
        .confirmationDialog("Sign out of Polished on this device?", isPresented: $confirmsSignOut, titleVisibility: .visible) {
            Button("Sign out", role: .destructive) { Task { await app.signOut() } }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        LabeledContent {
            Text(value).foregroundStyle(Color.ink2)
        } label: {
            Text(title).foregroundStyle(Color.ink)
        }
    }

    private func lastUsed(_ device: Device) -> String {
        let used = device.lastUsedAt.map { "Last used \(Words.day(String($0.prefix(10))) ?? $0)" } ?? "Not used yet"
        return "\(device.platform == "ios" ? "iPhone or iPad" : device.platform), \(used)"
    }

    private func syncLine(_ run: SyncRun) -> String {
        let when = Words.day(String((run.finishedAt ?? run.startedAt).prefix(10))) ?? ""
        switch run.status {
        case "ok": return "\(when), ok"
        case "error": return "\(when), failed"
        default: return "Running"
        }
    }
}
