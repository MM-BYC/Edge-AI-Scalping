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
                            HStack {
                                Text(position.symbol)
                                    .font(.headline)
                                Spacer()
                                Text("\(position.qty, specifier: "%.0f")")
                                    .fontWeight(.semibold)
                            }

                            HStack {
                                Text("Entry: $\(String(format: "%.2f", position.entryPrice))")
                                    .font(.caption)
                                Spacer()
                                Text("Current: $\(String(format: "%.2f", position.currentPrice))")
                                    .font(.caption)
                            }
                            .foregroundColor(.gray)

                            HStack {
                                Text("P&L")
                                    .font(.caption)
                                Spacer()
                                Text("$\(String(format: "%.2f", position.unrealizedPnl))")
                                    .foregroundColor(position.unrealizedPnl >= 0 ? .green : .red)
                                    .fontWeight(.semibold)
                                Text("(\(String(format: "%.2f", position.unrealizedPnlPct * 100))%)")
                                    .foregroundColor(position.unrealizedPnlPct >= 0 ? .green : .red)
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
