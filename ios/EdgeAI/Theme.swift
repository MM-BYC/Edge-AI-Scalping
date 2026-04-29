import SwiftUI

// MARK: - Hex color convenience

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8)  & 0xFF) / 255
        let b = Double(int         & 0xFF) / 255
        self.init(red: r, green: g, blue: b)
    }
}

// MARK: - App color palette

enum Theme {
    // Backgrounds
    static let background  = Color(hex: "080C18")   // deep navy black
    static let surface     = Color(hex: "111827")   // dark card
    static let surfaceAlt  = Color(hex: "1A2235")   // slightly lighter card

    // Brand accents
    static let cyan        = Color(hex: "00D8FF")   // electric cyan  – live data, signals
    static let gold        = Color(hex: "F59E0B")   // amber gold     – brand, warnings
    static let purple      = Color(hex: "8B5CF6")   // violet         – credit spreads
    static let teal        = Color(hex: "06B6D4")   // teal           – 0DTE

    // Semantic
    static let profit      = Color(hex: "10B981")   // emerald green
    static let loss        = Color(hex: "EF4444")   // coral red
    static let caution     = Color(hex: "F97316")   // orange

    // Text
    static let textPrimary = Color(hex: "F9FAFB")
    static let textMuted   = Color(hex: "6B7280")
}
