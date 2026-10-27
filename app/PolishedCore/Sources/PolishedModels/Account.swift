public struct UserBrief: Codable, Sendable, Hashable {
    public var sub: String
    public var name: String
}

public struct ServerInfo: Codable, Sendable, Hashable {
    public var version: String
    public var publicUrl: String
    public var storeUrl: String
    public var timezone: String
    public var overBlackAvailable: Bool
    public var shadeCount: Int
}

/// `GET /me`: the signed-in person and the server's facts.
public struct Me: Codable, Sendable, Hashable {
    public struct User: Codable, Sendable, Hashable {
        public var sub: String
        public var name: String
        public var firstName: String
    }

    public var user: User
    public var server: ServerInfo
}

/// `POST /auth/exchange`: the one-time code and the PKCE verifier for a device token.
public struct ExchangeRequest: Codable, Sendable, Hashable {
    public var code: String
    public var verifier: String
    public var deviceName: String
    public var platform: String
    public var appVersion: String

    public init(code: String, verifier: String, deviceName: String, platform: String = "ios", appVersion: String) {
        self.code = code
        self.verifier = verifier
        self.deviceName = deviceName
        self.platform = platform
        self.appVersion = appVersion
    }
}

public struct ExchangeResponse: Codable, Sendable, Hashable {
    public var token: String
    public var tokenId: Int
    public var user: UserBrief
}

public struct Device: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var deviceName: String
    public var platform: String
    public var createdAt: String
    public var lastUsedAt: String?
    public var current: Bool
}

/// `GET /auth/devices`.
public struct Devices: Codable, Sendable, Hashable {
    public var items: [Device]
}

public struct SyncRun: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var startedAt: String
    public var finishedAt: String?
    /// "running", "ok" or "error".
    public var status: String
    public var trigger: String
    public var pagesFetched: Int
    public var productsSeen: Int
    public var newShades: Int
    public var changedShades: Int
    public var newlyMissing: Int
    public var returned: Int
    public var unresolvedAliases: Int
    public var error: String?
}

/// `GET /sync`.
public struct SyncStatus: Codable, Sendable, Hashable {
    public var running: Bool
    public var last: SyncRun?
    public var runs: [SyncRun]
    public var cooldownUntil: String?
}
