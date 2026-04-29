import SwiftUI
import UIKit

@main
struct EdgeAIApp: App {
    let botService = BotService()

    init() {
        applyTabBarStyle()
        applyNavBarStyle()
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(botService)
        }
    }

    // MARK: - UIKit appearance

    private func applyTabBarStyle() {
        let active   = UIColor.systemBlue
        let inactive = UIColor.secondaryLabel

        let a = UITabBarAppearance()
        a.configureWithTransparentBackground()
        a.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterial)
        a.backgroundColor  = UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.031, green: 0.047, blue: 0.094, alpha: 0.75)
                : UIColor.systemBackground.withAlphaComponent(0.75)
        }
        a.stackedLayoutAppearance.selected.iconColor           = active
        a.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: active]
        a.stackedLayoutAppearance.normal.iconColor             = inactive
        a.stackedLayoutAppearance.normal.titleTextAttributes   = [.foregroundColor: inactive]

        UITabBar.appearance().standardAppearance   = a
        UITabBar.appearance().scrollEdgeAppearance = a
    }

    private func applyNavBarStyle() {
        let a = UINavigationBarAppearance()
        a.configureWithTransparentBackground()
        a.backgroundEffect     = UIBlurEffect(style: .systemUltraThinMaterial)
        a.backgroundColor      = UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.031, green: 0.047, blue: 0.094, alpha: 0.75)
                : UIColor.systemBackground.withAlphaComponent(0.75)
        }
        a.titleTextAttributes      = [.foregroundColor: UIColor.label]
        a.largeTitleTextAttributes = [.foregroundColor: UIColor.label]

        UINavigationBar.appearance().standardAppearance   = a
        UINavigationBar.appearance().scrollEdgeAppearance = a
        UINavigationBar.appearance().compactAppearance    = a
    }
}

// MARK: - Root tab view

struct ContentView: View {
    @EnvironmentObject var botService: BotService
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem { Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis") }
                .tag(0)

            PositionsView()
                .tabItem { Label("Positions", systemImage: "briefcase.fill") }
                .tag(1)

            ControlView()
                .tabItem { Label("Control", systemImage: "slider.horizontal.3") }
                .tag(2)

            TickersView()
                .tabItem { Label("Tickers", systemImage: "list.bullet.rectangle") }
                .tag(3)
        }
        .environmentObject(botService)
        .background(Theme.background.ignoresSafeArea())
    }
}
