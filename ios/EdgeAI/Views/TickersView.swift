import SwiftUI

private enum TickerTarget: String, CaseIterable, Identifiable {
    case equity       = "Equity"
    case sellPut      = "Sell Put"
    case creditSpread = "Credit Spread"
    var id: String { rawValue }
    var accentColor: Color {
        switch self {
        case .equity:       return .blue
        case .sellPut:      return .orange
        case .creditSpread: return .purple
        }
    }
}

struct TickersView: View {
    @EnvironmentObject var botService: BotService

    @State private var equityTickers:       [String] = stored("equityTickers",       default: ["SPY","QQQ","AAPL","TSLA","NVDA"])
    @State private var sellPutTickers:      [String] = stored("sellPutTickers",       default: ["TSLY","NVDY","AMZY"])
    @State private var creditSpreadTickers: [String] = stored("creditSpreadTickers",  default: ["SPY","QQQ"])

    @State private var newTicker   = ""
    @State private var addTarget:  TickerTarget = .equity
    @State private var appliedBanner = false

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {

                // ── Ticker lists ──────────────────────────────────────
                List {
                    tickerSection(
                        title: "EQUITY",
                        color: TickerTarget.equity.accentColor,
                        tickers: $equityTickers,
                        key: "equityTickers"
                    )
                    tickerSection(
                        title: "SELL PUT",
                        color: TickerTarget.sellPut.accentColor,
                        tickers: $sellPutTickers,
                        key: "sellPutTickers"
                    )
                    tickerSection(
                        title: "CREDIT SPREAD",
                        color: TickerTarget.creditSpread.accentColor,
                        tickers: $creditSpreadTickers,
                        key: "creditSpreadTickers"
                    )
                }
                .listStyle(.insetGrouped)

                // ── Add row ───────────────────────────────────────────
                VStack(spacing: 8) {
                    Picker("Add to", selection: $addTarget) {
                        ForEach(TickerTarget.allCases) { t in
                            Text(t.rawValue).tag(t)
                        }
                    }
                    .pickerStyle(.segmented)

                    HStack(spacing: 10) {
                        TextField("Symbol (e.g. MSFT)", text: $newTicker)
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
                                        ? .gray : addTarget.accentColor
                                )
                        }
                        .disabled(newTicker.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(Color(.systemBackground))

                // ── Confirmation banner ───────────────────────────────
                if appliedBanner {
                    Text("Tickers sent to bot")
                        .font(.caption).fontWeight(.semibold)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 6)
                        .background(Color.green)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // ── Apply button ──────────────────────────────────────
                Button(action: applyAll) {
                    HStack {
                        Image(systemName: "paperplane.fill")
                        Text("Apply All to Bot")
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
            .toolbar { EditButton() }
        }
    }

    // MARK: - Section builder

    @ViewBuilder
    private func tickerSection(
        title: String,
        color: Color,
        tickers: Binding<[String]>,
        key: String
    ) -> some View {
        Section {
            ForEach(tickers.wrappedValue, id: \.self) { ticker in
                HStack {
                    Text(ticker)
                        .font(.system(.body, design: .monospaced))
                        .fontWeight(.semibold)
                    Spacer()
                    Text(title)
                        .font(.caption2)
                        .foregroundColor(color)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 2)
                        .overlay(RoundedRectangle(cornerRadius: 4).stroke(color, lineWidth: 1))
                }
            }
            .onDelete { offsets in
                tickers.wrappedValue.remove(atOffsets: offsets)
                UserDefaults.standard.set(tickers.wrappedValue, forKey: key)
            }
        } header: {
            Text(title)
                .font(.caption)
                .foregroundColor(color)
                .fontWeight(.bold)
        }
    }

    // MARK: - Actions

    private func addTicker() {
        let sym = newTicker.trimmingCharacters(in: .whitespaces).uppercased()
        guard !sym.isEmpty else { return }
        switch addTarget {
        case .equity:
            guard !equityTickers.contains(sym) else { newTicker = ""; return }
            equityTickers.append(sym)
            UserDefaults.standard.set(equityTickers, forKey: "equityTickers")
        case .sellPut:
            guard !sellPutTickers.contains(sym) else { newTicker = ""; return }
            sellPutTickers.append(sym)
            UserDefaults.standard.set(sellPutTickers, forKey: "sellPutTickers")
        case .creditSpread:
            guard !creditSpreadTickers.contains(sym) else { newTicker = ""; return }
            creditSpreadTickers.append(sym)
            UserDefaults.standard.set(creditSpreadTickers, forKey: "creditSpreadTickers")
        }
        newTicker = ""
    }

    private func applyAll() {
        UserDefaults.standard.set(equityTickers,       forKey: "equityTickers")
        UserDefaults.standard.set(sellPutTickers,      forKey: "sellPutTickers")
        UserDefaults.standard.set(creditSpreadTickers, forKey: "creditSpreadTickers")
        botService.sendTickers(equityTickers)
        botService.sendOptionTickers(sellPut: sellPutTickers, creditSpread: creditSpreadTickers)
        withAnimation { appliedBanner = true }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            withAnimation { appliedBanner = false }
        }
    }
}

// MARK: - Helpers

private func stored(_ key: String, default def: [String]) -> [String] {
    UserDefaults.standard.stringArray(forKey: key) ?? def
}

struct TickersView_Previews: PreviewProvider {
    static var previews: some View {
        TickersView().environmentObject(BotService())
    }
}
