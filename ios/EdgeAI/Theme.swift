import SwiftUI
import UIKit

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
    static let background = Color(
        UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.031, green: 0.047, blue: 0.094, alpha: 1)
                : UIColor.systemGroupedBackground
        }
    )
    static let surface = Color(
        UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.067, green: 0.094, blue: 0.153, alpha: 1)
                : UIColor.secondarySystemGroupedBackground
        }
    )
    static let surfaceAlt = Color(
        UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.102, green: 0.133, blue: 0.208, alpha: 1)
                : UIColor.tertiarySystemGroupedBackground
        }
    )

    // Brand accents
    static let cyan        = Color(hex: "007AFF")   // system blue    – live data, signals
    static let gold        = Color(hex: "F59E0B")   // amber gold     – brand, warnings
    static let purple      = Color(hex: "8B5CF6")   // violet         – credit spreads
    static let teal        = Color(hex: "06B6D4")   // teal           – 0DTE

    // Semantic
    static let profit      = Color(hex: "10B981")   // emerald green
    static let loss        = Color(hex: "EF4444")   // coral red
    static let caution     = Color(hex: "F97316")   // orange

    // Text
    static let textPrimary = Color.primary
    static let textMuted   = Color.secondary

    // Adaptive effects
    static let separator = Color(
        UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor.white.withAlphaComponent(0.10)
                : UIColor.black.withAlphaComponent(0.10)
        }
    )
}

// MARK: - Glass card modifier

struct GlassCard: ViewModifier {
    var stroke: Color

    func body(content: Content) -> some View {
        content
            .background(.ultraThinMaterial)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(stroke, lineWidth: 0.6)
            )
    }
}

extension View {
    func glassCard(stroke: Color = Theme.separator) -> some View {
        modifier(GlassCard(stroke: stroke))
    }
}
