import SwiftUI

private enum TickerTarget: String, CaseIterable, Identifiable {
    case equity       = "Equity"
    case sellPut      = "Sell Put"
    case creditSpread = "Credit Spread"
    var id: String { rawValue }
    var accentColor: Color {
        switch self {
        case .equity:       return Theme.cyan
        case .sellPut:      return Theme.caution
        case .creditSpread: return Theme.purple
        }
    }
}

struct TickersView: View {
    @EnvironmentObject var botService: BotService

    @State private var equityTickers:       [String] = stored("equityTickers",       default: ["SPY","QQQ","AAPL","TSLA","NVDA"])
    @State private var sellPutTickers:      [String] = stored("sellPutTickers",       default: ["TSLY","NVDY","AMZY"])
    @State private var creditSpreadTickers: [String] = stored("creditSpreadTickers",  default: ["SPY","QQQ"])

    @State private var selectedCategory: TickerTarget = .equity
    @State private var newTicker     = ""
    @State private var appliedBanner = false

    private var activeTickers: Binding<[String]> {
        switch selectedCategory {
        case .equity:       return $equityTickers
        case .sellPut:      return $sellPutTickers
        case .creditSpread: return $creditSpreadTickers
        }
    }

    private var activeKey: String {
        switch selectedCategory {
        case .equity:       return "equityTickers"
        case .sellPut:      return "sellPutTickers"
        case .creditSpread: return "creditSpreadTickers"
        }
    }

    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()

                VStack(spacing: 0) {

                    // ── Category filter buttons ────────────────────────────
                    HStack(spacing: 8) {
                        ForEach(TickerTarget.allCases) { target in
                            Button(action: {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    selectedCategory = target
                                }
                            }) {
                                Text(target.rawValue)
                                    .font(.caption).fontWeight(.semibold)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 8)
                                    .background(
                                        selectedCategory == target
                                            ? target.accentColor.opacity(0.25)
                                            : Theme.surface.opacity(0.7)
                                    )
                                    .foregroundColor(
                                        selectedCategory == target
                                            ? target.accentColor
                                            : Theme.textMuted
                                    )
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8)
                                            .stroke(
                                                selectedCategory == target
                                                    ? target.accentColor.opacity(0.6)
                                                    : Color.clear,
                                                lineWidth: 1
                                            )
                                    )
                                    .cornerRadius(8)
                            }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial)

                    // ── Ticker list for selected category ─────────────────
                    List {
                        Section {
                            if activeTickers.wrappedValue.isEmpty {
                                Text("No tickers — add one below")
                                    .font(.caption).foregroundColor(Theme.textMuted)
                                    .listRowBackground(Color.clear)
                            } else {
                                ForEach(activeTickers.wrappedValue, id: \.self) { ticker in
                                    HStack {
                                        Text(ticker)
                                            .font(.system(.body, design: .monospaced))
                                            .fontWeight(.semibold)
                                            .foregroundColor(Theme.textPrimary)
                                        Spacer()
                                        Text(selectedCategory.rawValue.uppercased())
                                            .font(.caption2)
                                            .foregroundColor(selectedCategory.accentColor)
                                            .padding(.horizontal, 5).padding(.vertical, 2)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 4)
                                                    .stroke(selectedCategory.accentColor, lineWidth: 1)
                                            )
                                    }
                                    .listRowBackground(Theme.surface.opacity(0.7))
                                }
                                .onDelete { offsets in
                                    activeTickers.wrappedValue.remove(atOffsets: offsets)
                                    UserDefaults.standard.set(activeTickers.wrappedValue, forKey: activeKey)
                                }
                            }
                        } header: {
                            HStack {
                                Text(selectedCategory.rawValue.uppercased())
                                    .font(.caption).fontWeight(.bold)
                                    .foregroundColor(selectedCategory.accentColor)
                                Spacer()
                                Text("\(activeTickers.wrappedValue.count) ticker\(activeTickers.wrappedValue.count == 1 ? "" : "s")")
                                    .font(.caption2).foregroundColor(Theme.textMuted)
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                    .scrollContentBackground(.hidden)
                    .refreshable { await botService.refresh() }
                    .animation(.easeInOut(duration: 0.2), value: selectedCategory)

                    // ── Add row ───────────────────────────────────────────
                    VStack(spacing: 8) {
                        HStack(spacing: 10) {
                            TextField("Add symbol (e.g. MSFT)", text: $newTicker)
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
                                            ? Theme.textMuted : selectedCategory.accentColor
                                    )
                            }
                            .disabled(newTicker.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial)

                    // ── Confirmation banner ───────────────────────────────
                    if appliedBanner {
                        Text("Tickers sent to bot")
                            .font(.caption).fontWeight(.semibold).foregroundColor(.white)
                            .frame(maxWidth: .infinity).padding(.vertical, 6)
                            .background(Theme.profit)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    }

                    // ── Apply button ──────────────────────────────────────
                    Button(action: applyAll) {
                        HStack {
                            Image(systemName: "paperplane.fill")
                            Text("Apply All to Bot")
                        }
                        .frame(maxWidth: .infinity).padding()
                        .background(botService.isConnected ? Theme.cyan : Theme.textMuted)
                        .foregroundColor(botService.isConnected ? .black : .white)
                        .cornerRadius(10)
                    }
                    .disabled(!botService.isConnected)
                    .padding(.horizontal)
                    .padding(.bottom, 12)
                    .background(.ultraThinMaterial)
                }
            }
            .navigationTitle("Tickers")
            .toolbar { EditButton() }
        }
    }

    // MARK: - Actions

    private func addTicker() {
        let sym = newTicker.trimmingCharacters(in: .whitespaces).uppercased()
        guard !sym.isEmpty else { return }
        guard !activeTickers.wrappedValue.contains(sym) else { newTicker = ""; return }
        activeTickers.wrappedValue.append(sym)
        UserDefaults.standard.set(activeTickers.wrappedValue, forKey: activeKey)
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
