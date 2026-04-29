import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var botService: BotService
    @State private var lastConnAction: String? = nil

    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 14) {

                        // ── Connection status ─────────────────────────────
                        HStack {
                            Circle()
                                .fill(botService.isConnected ? Theme.profit : Theme.loss)
                                .frame(width: 8, height: 8)
                            Text(botService.connectionStatus).font(.caption)
                            Spacer()
                        }
                        .padding()
                        .glassCard()

                        // ── Bot status ────────────────────────────────────
                        if let status = botService.botStatus {
                            infoBlock {
                                row("Equity",       "$\(fmt2(status.equity))")
                                row("Cash",         "$\(fmt2(status.cash))")
                                row("Daily P&L",    "$\(fmt2(status.dailyPnl))",
                                    color: status.dailyPnl >= 0 ? Theme.profit : Theme.loss)
                                row("Positions",    "\(status.positions)")
                                row("Trades Today", "\(status.tradestoday)")
                            }
                        }

                        // ── Live Alpaca market data ───────────────────────
                        if !botService.marketData.isEmpty {
                            labelledBlock(label: "LIVE ALPACA DATA", labelColor: Theme.cyan) {
                                ForEach(botService.marketData.values.sorted { $0.symbol < $1.symbol }) { quote in
                                    row(quote.symbol, "$\(fmt2(quote.price))")
                                }
                            }
                        }

                        // ── Equity P&L stats ──────────────────────────────
                        if let pnl = botService.pnlStats {
                            infoBlock {
                                row("Total P&L",    "$\(fmt2(pnl.totalPnl))",
                                    color: pnl.totalPnl >= 0 ? Theme.profit : Theme.loss)
                                row("Win Rate",     "\(String(format: "%.1f", pnl.winRatePct))%")
                                row("Total Trades", "\(pnl.totalTrades)")
                            }
                        }

                        // ── Winning Ticker Traded ─────────────────────────
                        winnerBlock(label: "Winning Ticker Traded",
                                    ticker: botService.winningTicker, color: Theme.profit)

                        // ── Sell Put Option ───────────────────────────────
                        if let sp = botService.sellPutStats {
                            labelledBlock(label: "SELL PUT OPTION", labelColor: Theme.caution) {
                                row("Total P&L",  "$\(fmt2(sp.totalPnl))",
                                    color: sp.totalPnl >= 0 ? Theme.profit : Theme.loss)
                                row("Realized",   "$\(fmt2(sp.realizedPnl))")
                                row("Unrealized", "$\(fmt2(sp.unrealizedPnl))")
                                row("Open Pos.",  "\(sp.openPositions)")
                                row("Win Rate",   "\(String(format: "%.1f", sp.winRate * 100))%")
                            }
                        } else {
                            emptyOptionBlock(label: "SELL PUT OPTION", color: Theme.caution)
                        }

                        winnerBlock(label: "Winning SELL PUT",
                                    ticker: botService.winningSellPut, color: Theme.caution)

                        // ── Credit Spread Option ──────────────────────────
                        if let cs = botService.creditSpreadStats {
                            labelledBlock(label: "CREDIT SPREAD OPTION", labelColor: Theme.purple) {
                                row("Total P&L",  "$\(fmt2(cs.totalPnl))",
                                    color: cs.totalPnl >= 0 ? Theme.profit : Theme.loss)
                                row("Realized",   "$\(fmt2(cs.realizedPnl))")
                                row("Unrealized", "$\(fmt2(cs.unrealizedPnl))")
                                row("Open Pos.",  "\(cs.openPositions)")
                                row("Win Rate",   "\(String(format: "%.1f", cs.winRate * 100))%")
                            }
                        } else {
                            emptyOptionBlock(label: "CREDIT SPREAD OPTION", color: Theme.purple)
                        }

                        winnerBlock(label: "Winning Credit Spread",
                                    ticker: botService.winningCreditSpread, color: Theme.purple)

                        // ── 0DTE SPY Credit Spread ────────────────────────
                        if let dte = botService.zeroDTEStats {
                            labelledBlock(label: "0DTE SPY CREDIT SPREAD", labelColor: Theme.teal) {
                                row("Total P&L",  "$\(fmt2(dte.totalPnl))",
                                    color: dte.totalPnl >= 0 ? Theme.profit : Theme.loss)
                                row("Realized",   "$\(fmt2(dte.realizedPnl))")
                                row("Unrealized", "$\(fmt2(dte.unrealizedPnl))")
                                row("Open Pos.",  "\(dte.openPositions)")
                                row("Win Rate",   "\(String(format: "%.1f", dte.winRate * 100))%")
                            }
                        } else {
                            emptyOptionBlock(label: "0DTE SPY CREDIT SPREAD", color: Theme.teal)
                        }

                        winnerBlock(label: "Winning 0DTE",
                                    ticker: botService.winningZeroDTE, color: Theme.teal)

                        // ── Connect / Disconnect ──────────────────────────
                        if botService.isConnected {
                            Button(action: {
                                lastConnAction = "disconnect"
                                botService.disconnect()
                            }) {
                                Text("Disconnect from Bot")
                                    .frame(maxWidth: .infinity).padding()
                                    .background(lastConnAction == "disconnect"
                                                ? Color(white: 0.36) : Theme.loss)
                                    .foregroundColor(lastConnAction == "disconnect"
                                                     ? Color(white: 0.55) : .white)
                                    .cornerRadius(8)
                            }
                        } else {
                            Button(action: {
                                lastConnAction = "connect"
                                botService.connect(to: UserDefaults.standard
                                    .string(forKey: "botServerURL")
                                    ?? "ws://192.168.1.192:8765/ws/live")
                            }) {
                                Text("Connect to Bot")
                                    .frame(maxWidth: .infinity).padding()
                                    .background(lastConnAction == "connect"
                                                ? Color(white: 0.36) : Theme.cyan)
                                    .foregroundColor(lastConnAction == "connect"
                                                     ? Color(white: 0.55) : .black)
                                    .cornerRadius(8)
                            }
                        }
                    }
                    .padding()
                }
                .refreshable { await botService.refresh() }
            }
            .navigationTitle("Dashboard")
        }
    }

    // MARK: - Block builders

    @ViewBuilder
    private func infoBlock<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 12) { content() }
            .padding()
            .glassCard()
    }

    @ViewBuilder
    private func labelledBlock<Content: View>(
        label: String, labelColor: Color,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(label).font(.caption).fontWeight(.bold).foregroundColor(labelColor)
            content()
        }
        .padding()
        .glassCard(stroke: labelColor.opacity(0.4))
    }

    @ViewBuilder
    private func emptyOptionBlock(label: String, color: Color) -> some View {
        HStack {
            Text(label).font(.caption).fontWeight(.bold).foregroundColor(color)
            Spacer()
            Text("No data").font(.caption).foregroundColor(Theme.textMuted)
        }
        .padding()
        .glassCard(stroke: color.opacity(0.3))
    }

    @ViewBuilder
    private func winnerBlock(label: String, ticker: String?, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.caption).fontWeight(.bold).foregroundColor(color)
            Text(ticker ?? "--")
                .font(.largeTitle).fontWeight(.bold)
                .foregroundColor(ticker != nil ? color : Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .glassCard(stroke: color.opacity(0.3))
    }

    @ViewBuilder
    private func row(_ label: String, _ value: String, color: Color = .primary) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value).fontWeight(.semibold).foregroundColor(color)
        }
    }

    private func fmt2(_ v: Double) -> String { String(format: "%.2f", v) }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView().environmentObject(BotService())
    }
}
