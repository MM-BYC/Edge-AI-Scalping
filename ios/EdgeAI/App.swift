import SwiftUI

@main
struct EdgeAIApp: App {
    let botService = BotService()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(botService)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var botService: BotService
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.line.uptrend.xyaxis")
                }
                .tag(0)

            PositionsView()
                .tabItem {
                    Label("Positions", systemImage: "briefcase.fill")
                }
                .tag(1)

            ControlView()
                .tabItem {
                    Label("Control", systemImage: "slider.horizontal.3")
                }
                .tag(2)

            TickersView()
                .tabItem {
                    Label("Tickers", systemImage: "list.bullet.rectangle")
                }
                .tag(3)
        }
        .environmentObject(botService)
    }
}
