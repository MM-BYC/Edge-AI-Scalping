import SwiftUI

struct PositionsView: View {
    @EnvironmentObject var botService: BotService

    var body: some View {
        NavigationView {
            ScrollView {
                LazyVStack(spacing: 12, pinnedViews: .sectionHeaders) {

                    // ── Equity Positions ──────────────────────────────
                    Section {
                        if botService.positions.isEmpty {
                            emptyCard("No open equity positions")
                        } else {
                            ForEach(botService.positions) { pos in
                                equityCard(pos)
                            }
                        }
                    } header: {
                        sectionHeader("EQUITY POSITIONS", color: .blue)
                    }

                    // ── Sell Put Positions ────────────────────────────
                    Section {
                        if botService.sellPutPositions.isEmpty {
                            emptyCard("No open sell put positions")
                        } else {
                            ForEach(botService.sellPutPositions) { pos in
                                optionCard(pos)
                            }
                        }
                    } header: {
                        sectionHeader("SELL PUT OPTION", color: .orange)
                    }

                    // ── Credit Spread Positions ───────────────────────
                    Section {
                        if botService.creditSpreadPositions.isEmpty {
                            emptyCard("No open credit spread positions")
                        } else {
                            ForEach(botService.creditSpreadPositions) { pos in
                                optionCard(pos)
                            }
                        }
                    } header: {
                        sectionHeader("CREDIT SPREAD OPTION", color: .purple)
                    }

                    // ── 0DTE Positions ────────────────────────────────
                    Section {
                        if botService.zeroDTEPositions.isEmpty {
                            emptyCard("No open 0DTE positions")
                        } else {
                            ForEach(botService.zeroDTEPositions) { pos in
                                optionCard(pos)
                            }
                        }
                    } header: {
                        sectionHeader("0DTE SPY CREDIT SPREAD", color: .cyan)
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 16)
            }
            .navigationTitle("Positions")
        }
    }

    // MARK: - Equity card

    @ViewBuilder
    private func equityCard(_ pos: Position) -> some View {
        let winning = pos.unrealizedPnl >= 0
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(pos.symbol).font(.headline)
                Spacer()
                Text("\(pos.qty, specifier: "%.0f")sh").fontWeight(.semibold)
            }
            HStack {
                Text("Entry: $\(String(format: "%.2f", pos.entryPrice))").font(.caption)
                Spacer()
                Text("Current: $\(String(format: "%.2f", pos.currentPrice))").font(.caption)
            }
            .foregroundColor(.gray)
            HStack(spacing: 6) {
                Text("P&L").font(.caption)
                Spacer()
                wlBadge(winning)
                Text("$\(String(format: "%.2f", pos.unrealizedPnl))")
                    .foregroundColor(winning ? .green : .red).fontWeight(.semibold)
                Text("(\(String(format: "%.2f", pos.unrealizedPnlPct * 100))%)")
                    .foregroundColor(winning ? .green : .red).font(.caption)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }

    // MARK: - Option card

    @ViewBuilder
    private func optionCard(_ pos: OptionPosition) -> some View {
        let winning = pos.unrealizedPnl >= 0
        let stratLabel: String = {
            switch pos.strategy {
            case "sell_put":      return "SELL PUT"
            case "0dte":          return "0DTE"
            default:              return "CREDIT SPREAD"
            }
        }()
        let stratColor: Color = {
            switch pos.strategy {
            case "sell_put": return .orange
            case "0dte":     return .cyan
            default:         return .purple
            }
        }()

        VStack(alignment: .leading, spacing: 8) {
            // Symbol + strategy badge
            HStack {
                Text(pos.symbol).font(.headline)
                Text(stratLabel)
                    .font(.caption2).fontWeight(.bold)
                    .foregroundColor(.white)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(stratColor).cornerRadius(4)
                Spacer()
                Text("\(pos.qty) contract\(pos.qty == 1 ? "" : "s")")
                    .font(.caption).foregroundColor(.gray)
            }

            // Strike / expiry
            HStack {
                if let upper = pos.upperStrike {
                    Text("Strikes: $\(String(format: "%.0f", pos.strike)) / $\(String(format: "%.0f", upper))")
                        .font(.caption)
                } else {
                    Text("Strike: $\(String(format: "%.0f", pos.strike))").font(.caption)
                }
                Spacer()
                Text("Exp: \(pos.expiry)  \(pos.daysToExpiry)d").font(.caption)
            }
            .foregroundColor(.gray)

            // Premium vs current
            HStack {
                Text("Premium: $\(String(format: "%.2f", pos.premiumCollected))").font(.caption)
                Spacer()
                Text("Mark: $\(String(format: "%.2f", pos.currentValue))").font(.caption)
            }
            .foregroundColor(.gray)

            // Greeks
            HStack {
                Text("Δ \(String(format: "%.3f", pos.delta))").font(.caption).foregroundColor(.gray)
                Text("Θ \(String(format: "%.3f", pos.theta))").font(.caption).foregroundColor(.gray)
                Spacer()
                wlBadge(winning)
                Text("$\(String(format: "%.2f", pos.unrealizedPnl))")
                    .foregroundColor(winning ? .green : .red).fontWeight(.semibold)
                Text("(\(String(format: "%.1f", pos.unrealizedPnlPct * 100))%)")
                    .foregroundColor(winning ? .green : .red).font(.caption)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }

    // MARK: - Helpers

    @ViewBuilder
    private func sectionHeader(_ title: String, color: Color) -> some View {
        HStack {
            Text(title)
                .font(.caption).fontWeight(.bold).foregroundColor(color)
            Spacer()
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 6)
        .background(Color(.systemBackground))
    }

    @ViewBuilder
    private func emptyCard(_ message: String) -> some View {
        Text(message)
            .font(.caption).foregroundColor(.gray)
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(10)
    }

    @ViewBuilder
    private func wlBadge(_ winning: Bool) -> some View {
        Text(winning ? "W" : "L")
            .font(.caption).fontWeight(.bold).foregroundColor(.white)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(winning ? Color.green : Color.red)
            .cornerRadius(4)
    }
}

struct PositionsView_Previews: PreviewProvider {
    static var previews: some View {
        PositionsView().environmentObject(BotService())
    }
}
