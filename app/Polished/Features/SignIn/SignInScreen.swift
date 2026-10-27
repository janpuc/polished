import AuthenticationServices
import PolishedAPI
import PolishedModels
import SwiftUI

/// The first screen of a signed-out app: the mark, the name and one filled button that runs the
/// Pocket ID sign-in (docs/NATIVE.md 2.4).
struct SignInScreen: View {
    @Environment(AppModel.self) private var app
    @Environment(\.webAuthenticationSession) private var webAuthenticationSession
    @State private var isSigningIn = false
    @State private var failure: String?

    var body: some View {
        ZStack {
            Color.board.ignoresSafeArea()
            VStack(spacing: 0) {
                Spacer()
                VStack(spacing: 20) {
                    Image("Mark")
                        .resizable()
                        .frame(width: 96, height: 96)
                        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                        .shadow(color: Color.shadowInk.opacity(0.25), radius: 18, y: 8)
                        .accessibilityHidden(true)
                    Text("Polished")
                        .displayFont(.greeting)
                        .foregroundStyle(Color.ink)
                        .accessibilityAddTraits(.isHeader)
                    Text("Your swatch book, lit.")
                        .font(.body)
                        .foregroundStyle(Color.ink2)
                }
                Spacer()
                VStack(spacing: 12) {
                    if let message = failure ?? app.session.notice {
                        Text(message)
                            .font(.subheadline)
                            .foregroundStyle(Color.bad)
                            .multilineTextAlignment(.center)
                            .accessibilityIdentifier("sign-in-message")
                    }
                    Button {
                        Task { await signIn() }
                    } label: {
                        if isSigningIn {
                            ProgressView().tint(Color.primaryOn)
                        } else {
                            Text("Sign in with Pocket ID")
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(isSigningIn)
                    .accessibilityIdentifier("sign-in-button")
                    Text(app.serverURL.host(percentEncoded: false) ?? "")
                        .font(.footnote)
                        .foregroundStyle(Color.ink3)
                }
                .frame(maxWidth: 420)
                .padding(.horizontal, 24)
                .padding(.bottom, 32)
            }
        }
    }

    /// `/auth/app/start` in a browser session shared with Safari (so the passkey is remembered),
    /// back through the claimed https callback, then the code for a device token.
    private func signIn() async {
        isSigningIn = true
        failure = nil
        defer { isSigningIn = false }
        do {
            let flow = SignInFlow(server: app.serverURL, deviceName: AppModel.deviceName)
            let code = try await flow.authenticate(using: webAuthenticationSession)
            let response = try await app.api.exchange(
                ExchangeRequest(
                    code: code, verifier: flow.verifier, deviceName: AppModel.deviceName,
                    appVersion: AppModel.version))
            try await app.finishSignIn(response)
        } catch let error as ASWebAuthenticationSessionError where error.code == .canceledLogin {
            return
        } catch let error as APIError {
            failure = error.message
        } catch {
            failure = "Couldn't sign in. Try again."
        }
    }
}

/// One sign-in attempt: the PKCE verifier lives here and nowhere else.
struct SignInFlow {
    let server: URL
    let deviceName: String
    let verifier = PKCE.makeVerifier()

    enum Failure: Error {
        case noCode
    }

    var startURL: URL {
        var components = URLComponents(url: server.appending(path: "/auth/app/start"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "challenge", value: PKCE.challenge(for: verifier)),
            URLQueryItem(name: "device", value: deviceName),
        ]
        return components.url!
    }

    /// Runs the browser session; the one-time code in the callback's query.
    @MainActor
    func authenticate(using session: WebAuthenticationSession) async throws -> String {
        let callback = ASWebAuthenticationSession.Callback.https(
            host: server.host(percentEncoded: false) ?? "", path: "/auth/app/callback")
        let url = try await session.authenticate(
            using: startURL, callback: callback, preferredBrowserSession: .shared, additionalHeaderFields: [:])
        guard let code = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?
            .first(where: { $0.name == "code" })?.value, !code.isEmpty
        else { throw Failure.noCode }
        return code
    }
}
