import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var botService: BotService

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 14) {

                    // ── Connection status ─────────────────────────────
                    HStack {
                        Circle()
                            .fill(botService.isConnected ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(botService.connectionStatus).font(.caption)
                        Spacer()
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)

                    // ── Bot status ────────────────────────────────────
                    if let status = botService.botStatus {
                        infoBlock {
                            row("Equity",       "$\(fmt2(status.equity))")
                            row("Daily P&L",    "$\(fmt2(status.dailyPnl))",
                                color: status.dailyPnl >= 0 ? .green : .red)
                            row("Positions",    "\(status.positions)")
                            row("Trades Today", "\(status.tradestoday)")
                        }
                    }

                    // ── Equity P&L stats ──────────────────────────────
                    if let pnl = botService.pnlStats {
                        infoBlock {
                            row("Total P&L",    "$\(fmt2(pnl.totalPnl))",
                                color: pnl.totalPnl >= 0 ? .green : .red)
                            row("Win Rate",     "\(String(format: "%.1f", pnl.winRatePct))%")
                            row("Total Trades", "\(pnl.totalTrades)")
                        }
                    }

                    // ── Winning Ticker Traded ─────────────────────────
                    winnerBlock(
                        label: "Winning Ticker Traded",
                        ticker: botService.winningTicker,
                        color: .green
                    )

                    // ── Sell Put Option ───────────────────────────────
                    if let sp = botService.sellPutStats {
                        labelledBlock(label: "SELL PUT OPTION", labelColor: .orange) {
                            row("Total P&L",   "$\(fmt2(sp.totalPnl))",
                                color: sp.totalPnl >= 0 ? .green : .red)
                            row("Realized",    "$\(fmt2(sp.realizedPnl))")
                            row("Unrealized",  "$\(fmt2(sp.unrealizedPnl))")
                            row("Open Pos.",   "\(sp.openPositions)")
                            row("Win Rate",    "\(String(format: "%.1f", sp.winRate * 100))%")
                        }
                    } else {
                        emptyOptionBlock(label: "SELL PUT OPTION", color: .orange)
                    }

                    winnerBlock(
                        label: "Winning SELL PUT",
                        ticker: botService.winningSellPut,
                        color: .orange
                    )

                    // ── Credit Spread Option ──────────────────────────
                    if let cs = botService.creditSpreadStats {
                        labelledBlock(label: "CREDIT SPREAD OPTION", labelColor: .purple) {
                            row("Total P&L",   "$\(fmt2(cs.totalPnl))",
                                color: cs.totalPnl >= 0 ? .green : .red)
                            row("Realized",    "$\(fmt2(cs.realizedPnl))")
                            row("Unrealized",  "$\(fmt2(cs.unrealizedPnl))")
                            row("Open Pos.",   "\(cs.openPositions)")
                            row("Win Rate",    "\(String(format: "%.1f", cs.winRate * 100))%")
                        }
                    } else {
                        emptyOptionBlock(label: "CREDIT SPREAD OPTION", color: .purple)
                    }

                    winnerBlock(
                        label: "Winning Credit Spread",
                        ticker: botService.winningCreditSpread,
                        color: .purple
                    )

                    // ── 0DTE SPY Credit Spread ────────────────────────
                    if let dte = botService.zeroDTEStats {
                        labelledBlock(label: "0DTE SPY CREDIT SPREAD", labelColor: .cyan) {
                            row("Total P&L",   "$\(fmt2(dte.totalPnl))",
                                color: dte.totalPnl >= 0 ? .green : .red)
                            row("Realized",    "$\(fmt2(dte.realizedPnl))")
                            row("Unrealized",  "$\(fmt2(dte.unrealizedPnl))")
                            row("Open Pos.",   "\(dte.openPositions)")
                            row("Win Rate",    "\(String(format: "%.1f", dte.winRate * 100))%")
                        }
                    } else {
                        emptyOptionBlock(label: "0DTE SPY CREDIT SPREAD", color: .cyan)
                    }

                    winnerBlock(
                        label: "Winning 0DTE",
                        ticker: botService.winningZeroDTE,
                        color: .cyan
                    )

                    // ── Connect / Disconnect ──────────────────────────
                    if botService.isConnected {
                        Button(action: { botService.disconnect() }) {
                            Text("Disconnect from Bot")
                                .frame(maxWidth: .infinity).padding()
                                .background(Color.red).foregroundColor(.white).cornerRadius(8)
                        }
                    } else {
                        Button(action: {
                            botService.connect(to: UserDefaults.standard
                                .string(forKey: "botServerURL")
                                ?? "ws://192.168.1.192:8765/ws/live")
                        }) {
                            Text("Connect to Bot")
                                .frame(maxWidth: .infinity).padding()
                                .background(Color.blue).foregroundColor(.white).cornerRadius(8)
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Dashboard")
        }
    }

    // MARK: - Block builders

    @ViewBuilder
    private func infoBlock<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 12) { content() }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(8)
    }

    @ViewBuilder
    private func labelledBlock<Content: View>(
        label: String,
        labelColor: Color,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(label)
                .font(.caption).fontWeight(.bold).foregroundColor(labelColor)
            content()
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(labelColor.opacity(0.4), lineWidth: 1))
    }

    @ViewBuilder
    private func emptyOptionBlock(label: String, color: Color) -> some View {
        HStack {
            Text(label).font(.caption).fontWeight(.bold).foregroundColor(color)
            Spacer()
            Text("No data").font(.caption).foregroundColor(.gray)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(color.opacity(0.3), lineWidth: 1))
    }

    @ViewBuilder
    private func winnerBlock(label: String, ticker: String?, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.caption).fontWeight(.bold).foregroundColor(color)
            Text(ticker ?? "--")
                .font(.largeTitle).fontWeight(.bold)
                .foregroundColor(ticker != nil ? color : .gray)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(color.opacity(0.3), lineWidth: 1))
    }

    // MARK: - Row helper

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
