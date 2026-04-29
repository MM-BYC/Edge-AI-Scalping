import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var botService: BotService

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                // Connection Status
                HStack {
                    Circle()
                        .fill(botService.isConnected ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(botService.connectionStatus)
                        .font(.caption)
                    Spacer()
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)

                // Bot Status
                if let status = botService.botStatus {
                    VStack(spacing: 12) {
                        HStack {
                            Text("Equity")
                            Spacer()
                            Text("$\(String(format: "%.2f", status.equity))")
                                .fontWeight(.semibold)
                        }

                        HStack {
                            Text("Daily P&L")
                            Spacer()
                            Text("$\(String(format: "%.2f", status.dailyPnl))")
                                .foregroundColor(status.dailyPnl >= 0 ? .green : .red)
                                .fontWeight(.semibold)
                        }

                        HStack {
                            Text("Positions")
                            Spacer()
                            Text("\(status.positions)")
                        }

                        HStack {
                            Text("Trades Today")
                            Spacer()
                            Text("\(status.tradestoday)")
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }

                // P&L Stats
                if let pnl = botService.pnlStats {
                    VStack(spacing: 12) {
                        HStack {
                            Text("Total P&L")
                            Spacer()
                            Text("$\(String(format: "%.2f", pnl.totalPnl))")
                                .foregroundColor(pnl.totalPnl >= 0 ? .green : .red)
                                .fontWeight(.semibold)
                        }

                        HStack {
                            Text("Win Rate")
                            Spacer()
                            Text("\(String(format: "%.1f", pnl.winRatePct))%")
                        }

                        HStack {
                            Text("Total Trades")
                            Spacer()
                            Text("\(pnl.totalTrades)")
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }

                Spacer()

                // Connect Button
                if !botService.isConnected {
                    Button(action: {
                        botService.connect(to: "ws://192.168.1.100:8765")
                    }) {
                        Text("Connect to Bot")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                    }
                }
            }
            .padding()
            .navigationTitle("Dashboard")
        }
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
            .environmentObject(BotService())
    }
}
