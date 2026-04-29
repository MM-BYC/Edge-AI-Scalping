import SwiftUI

struct TickersView: View {
    @EnvironmentObject var botService: BotService

    @State private var tickers: [String] = (
        UserDefaults.standard.stringArray(forKey: "watchedTickers")
        ?? ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]
    )
    @State private var newTicker   = ""
    @State private var appliedBanner = false

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {

                // Ticker list
                List {
                    ForEach(tickers, id: \.self) { ticker in
                        HStack {
                            Text(ticker)
                                .font(.system(.body, design: .monospaced))
                                .fontWeight(.semibold)
                            Spacer()
                        }
                    }
                    .onDelete(perform: deleteTicker)
                }
                .listStyle(.insetGrouped)

                // Add-ticker row
                HStack(spacing: 10) {
                    TextField("Ticker symbol (e.g. MSFT)", text: $newTicker)
                        .textFieldStyle(.roundedBorder)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .submitLabel(.done)
                        .onSubmit(addTicker)

                    Button(action: addTicker) {
                        Image(systemName: "plus.circle.fill")
                            .font(.title2)
                            .foregroundColor(
                                newTicker.trimmingCharacters(in: .whitespaces).isEmpty
                                    ? .gray : .blue
                            )
                    }
                    .disabled(newTicker.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(Color(.systemBackground))

                // Applied confirmation banner
                if appliedBanner {
                    Text("Tickers sent to bot")
                        .font(.caption)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                        .background(Color.green)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // Apply button
                Button(action: applyTickers) {
                    HStack {
                        Image(systemName: "paperplane.fill")
                        Text("Apply to Bot")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(botService.isConnected ? Color.blue : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                }
                .disabled(!botService.isConnected)
                .padding(.horizontal)
                .padding(.bottom, 12)
            }
            .navigationTitle("Tickers")
            .toolbar {
                EditButton()
            }
        }
    }

    // MARK: - Actions

    private func addTicker() {
        let symbol = newTicker
            .trimmingCharacters(in: .whitespaces)
            .uppercased()
        guard !symbol.isEmpty, !tickers.contains(symbol) else {
            newTicker = ""
            return
        }
        tickers.append(symbol)
        newTicker = ""
        saveTickers()
    }

    private func deleteTicker(at offsets: IndexSet) {
        tickers.remove(atOffsets: offsets)
        saveTickers()
    }

    private func saveTickers() {
        UserDefaults.standard.set(tickers, forKey: "watchedTickers")
    }

    private func applyTickers() {
        saveTickers()
        botService.sendTickers(tickers)
        withAnimation {
            appliedBanner = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            withAnimation {
                appliedBanner = false
            }
        }
    }
}

struct TickersView_Previews: PreviewProvider {
    static var previews: some View {
        TickersView()
            .environmentObject(BotService())
    }
}
