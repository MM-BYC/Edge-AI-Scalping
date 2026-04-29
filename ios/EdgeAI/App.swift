import SwiftUI

@main
struct EdgeAIApp: App {
    let botService = BotService()
    @State private var splashDone = false

    init() {
        applyTabBarStyle()
        applyNavBarStyle()
    }

    var body: some Scene {
        WindowGroup {
            ZStack {
                ContentView()
                    .environmentObject(botService)
                    .opacity(splashDone ? 1 : 0)

                if !splashDone {
                    SplashView()
                        .transition(.opacity)
                        .zIndex(1)
                }
            }
            .preferredColorScheme(.dark)
            .onAppear {
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) {
                    withAnimation(.easeInOut(duration: 0.7)) {
                        splashDone = true
                    }
                }
            }
        }
    }

    // MARK: - UIKit appearance

    private func applyTabBarStyle() {
        let bg       = UIColor(red: 0.031, green: 0.047, blue: 0.094, alpha: 1)  // #080C18
        let active   = UIColor(red: 0,     green: 0.847, blue: 1,     alpha: 1)  // #00D8FF
        let inactive = UIColor(red: 0.42,  green: 0.45,  blue: 0.50,  alpha: 1)

        let a = UITabBarAppearance()
        a.configureWithOpaqueBackground()
        a.backgroundColor = bg
        a.stackedLayoutAppearance.selected.iconColor           = active
        a.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: active]
        a.stackedLayoutAppearance.normal.iconColor             = inactive
        a.stackedLayoutAppearance.normal.titleTextAttributes   = [.foregroundColor: inactive]

        UITabBar.appearance().standardAppearance   = a
        UITabBar.appearance().scrollEdgeAppearance = a
    }

    private func applyNavBarStyle() {
        let bg = UIColor(red: 0.031, green: 0.047, blue: 0.094, alpha: 1)

        let a = UINavigationBarAppearance()
        a.configureWithOpaqueBackground()
        a.backgroundColor          = bg
        a.titleTextAttributes      = [.foregroundColor: UIColor.white]
        a.largeTitleTextAttributes = [.foregroundColor: UIColor.white]

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
