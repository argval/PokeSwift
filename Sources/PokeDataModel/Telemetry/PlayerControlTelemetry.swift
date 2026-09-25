import Foundation

public struct OakIntroTelemetry: Codable, Equatable, Sendable {
    public let phase: String
    public let pageIndex: Int
    public let pageCount: Int
    public let presets: [String]
    public let focusedIndex: Int
    public let isTypingCustomName: Bool

    public init(
        phase: String,
        pageIndex: Int,
        pageCount: Int,
        presets: [String],
        focusedIndex: Int,
        isTypingCustomName: Bool
    ) {
        self.phase = phase
        self.pageIndex = pageIndex
        self.pageCount = pageCount
        self.presets = presets
        self.focusedIndex = focusedIndex
        self.isTypingCustomName = isTypingCustomName
    }
}

public struct NicknamePromptTelemetry: Codable, Equatable, Sendable {
    public let speciesID: String
    public let defaultName: String
    public let focusedIndex: Int

    public init(speciesID: String, defaultName: String, focusedIndex: Int) {
        self.speciesID = speciesID
        self.defaultName = defaultName
        self.focusedIndex = focusedIndex
    }
}
