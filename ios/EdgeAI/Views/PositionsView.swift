import SwiftUI

struct PositionsView: View {
    @EnvironmentObject var botService: BotService

    var body: some View {
        NavigationView {
            VStack {
                if botService.positions.isEmpty {
                    VStack {
                        Text("No Open Positions")
                            .font(.headline)
                        Text("Positions will appear here when the bot enters trades")
                            .font(.caption)
                            .foregroundColor(.gray)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List(botService.positions) { position in
                        VStack(alignment: .leading, spacing: 8) {

                            // Symbol + quantity
                            HStack {
                                Text(position.symbol)
                                    .font(.headline)
                                Spacer()
                                Text("\(position.qty, specifier: "%.0f")sh")
                                    .fontWeight(.semibold)
                            }

                            // Entry / current prices
                            HStack {
                                Text("Entry: $\(String(format: "%.2f", position.entryPrice))")
                                    .font(.caption)
                                Spacer()
                                Text("Current: $\(String(format: "%.2f", position.currentPrice))")
                                    .font(.caption)
                            }
                            .foregroundColor(.gray)

                            // P&L row with W / L badge
                            HStack(spacing: 6) {
                                Text("P&L")
                                    .font(.caption)
                                Spacer()

                                // W or L badge
                                let winning = position.unrealizedPnl >= 0
                                Text(winning ? "W" : "L")
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(winning ? Color.green : Color.red)
                                    .cornerRadius(4)

                                Text("$\(String(format: "%.2f", position.unrealizedPnl))")
                                    .foregroundColor(winning ? .green : .red)
                                    .fontWeight(.semibold)

                                Text("(\(String(format: "%.2f", position.unrealizedPnlPct * 100))%)")
                                    .foregroundColor(winning ? .green : .red)
                                    .font(.caption)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .navigationTitle("Positions")
        }
    }
}

struct PositionsView_Previews: PreviewProvider {
    static var previews: some View {
        PositionsView()
            .environmentObject(BotService())
    }
}
