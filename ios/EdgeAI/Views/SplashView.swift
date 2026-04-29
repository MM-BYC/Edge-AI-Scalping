import SwiftUI

// MARK: - Splash screen

struct SplashView: View {
    @State private var appeared = false
    @State private var glowing  = false
    @State private var pulsing  = false

    var body: some View {
        ZStack {
            // ── Background ─────────────────────────────────────────────
            LinearGradient(
                colors: [Color(hex: "080C18"), Color(hex: "0B1628"), Color(hex: "080C18")],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            GridLines()
                .ignoresSafeArea()

            CandleBackground()
                .ignoresSafeArea()

            // Soft cyan radial glow centred on the wordmark
            RadialGradient(
                colors: [Theme.cyan.opacity(0.10), .clear],
                center: .center,
                startRadius: 0,
                endRadius: 220
            )
            .frame(width: 440, height: 440)

            // ── Wordmark ───────────────────────────────────────────────
            VStack(spacing: 0) {

                // Pulsing ring dot
                ZStack {
                    Circle()
                        .stroke(Theme.cyan.opacity(pulsing ? 0 : 0.6), lineWidth: 1.5)
                        .frame(width: 28, height: 28)
                        .scaleEffect(pulsing ? 2.8 : 1.0)
                        .animation(
                            .easeOut(duration: 1.4).repeatForever(autoreverses: false),
                            value: pulsing
                        )
                    Circle()
                        .fill(Theme.cyan)
                        .frame(width: 8, height: 8)
                }
                .padding(.bottom, 36)

                // "STOCK"
                Text("STOCK")
                    .font(.system(size: 66, weight: .black, design: .rounded))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Theme.cyan, Color(hex: "0099BB")],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .shadow(
                        color: Theme.cyan.opacity(glowing ? 0.85 : 0.30),
                        radius: glowing ? 28 : 10
                    )
                    .animation(
                        .easeInOut(duration: 1.9).repeatForever(autoreverses: true),
                        value: glowing
                    )

                // Gold divider
                Rectangle()
                    .fill(
                        LinearGradient(
                            colors: [.clear, Theme.gold, .clear],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(height: 1)
                    .padding(.horizontal, 44)
                    .padding(.vertical, 12)

                // "SCALPER"
                Text("SCALPER")
                    .font(.system(size: 27, weight: .semibold, design: .rounded))
                    .kerning(9)
                    .foregroundColor(Theme.gold)

                // Subtitle
                Text("E D G E  A I")
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundColor(Theme.textMuted)
                    .padding(.top, 22)
            }
            .opacity(appeared ? 1 : 0)
            .scaleEffect(appeared ? 1.0 : 0.90)
            .animation(.spring(response: 0.7, dampingFraction: 0.8), value: appeared)
        }
        .onAppear {
            appeared = true
            pulsing  = true
            glowing  = true
        }
    }
}

// MARK: - Grid background

private struct GridLines: View {
    var body: some View {
        Canvas { ctx, size in
            let step: CGFloat = 44
            var x: CGFloat = 0
            while x <= size.width {
                var p = Path()
                p.move(to: CGPoint(x: x, y: 0))
                p.addLine(to: CGPoint(x: x, y: size.height))
                ctx.stroke(p, with: .color(.white.opacity(0.032)), lineWidth: 0.5)
                x += step
            }
            var y: CGFloat = 0
            while y <= size.height {
                var p = Path()
                p.move(to: CGPoint(x: 0, y: y))
                p.addLine(to: CGPoint(x: size.width, y: y))
                ctx.stroke(p, with: .color(.white.opacity(0.032)), lineWidth: 0.5)
                y += step
            }
        }
    }
}

// MARK: - Candlestick silhouette background

private struct CandleBackground: View {
    // (isUp, bodyTop, bodyBottom) — fractions of screen height (0 = top, 1 = bottom)
    private let candles: [(Bool, CGFloat, CGFloat)] = [
        (true,  0.44, 0.60), (false, 0.38, 0.58), (true,  0.46, 0.64),
        (false, 0.40, 0.56), (true,  0.36, 0.54), (false, 0.45, 0.66),
        (true,  0.42, 0.60), (false, 0.38, 0.62), (true,  0.40, 0.56),
        (false, 0.35, 0.58), (true,  0.46, 0.65), (false, 0.39, 0.57),
        (true,  0.43, 0.61), (false, 0.41, 0.63), (true,  0.37, 0.53),
        (false, 0.44, 0.67), (true,  0.41, 0.57), (false, 0.38, 0.60),
        (true,  0.45, 0.63), (false, 0.36, 0.55),
    ]

    var body: some View {
        GeometryReader { geo in
            Canvas { ctx, size in
                let count = candles.count
                let colW  = size.width / CGFloat(count)

                for (i, (isUp, topFrac, botFrac)) in candles.enumerated() {
                    let cx     = colW * CGFloat(i) + colW * 0.5
                    let bodyW  = colW * 0.44
                    let yTop   = size.height * topFrac
                    let yBot   = size.height * botFrac
                    let bodyH  = max(4, yBot - yTop)
                    let wick   = bodyH * 0.38

                    let color: GraphicsContext.Shading = isUp
                        ? .color(Color(hex: "10B981").opacity(0.22))
                        : .color(Color(hex: "EF4444").opacity(0.22))

                    // Wick
                    ctx.fill(
                        Path(CGRect(x: cx - 1, y: yTop - wick, width: 2, height: bodyH + wick * 2)),
                        with: color
                    )
                    // Body
                    var body = Path()
                    body.addRoundedRect(
                        in: CGRect(x: cx - bodyW / 2, y: yTop, width: bodyW, height: bodyH),
                        cornerSize: CGSize(width: 2, height: 2)
                    )
                    ctx.fill(body, with: color)
                }
            }
        }
    }
}

// MARK: - Preview

struct SplashView_Previews: PreviewProvider {
    static var previews: some View {
        SplashView()
            .preferredColorScheme(.dark)
    }
}
