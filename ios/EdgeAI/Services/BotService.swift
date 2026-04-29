import Foundation

class BotService: NSObject, ObservableObject, URLSessionWebSocketDelegate {
    @Published var isConnected      = false
    @Published var botStatus:       BotStatus?
    @Published var positions:       [Position]       = []
    @Published var pnlStats:        PnLStats?
    @Published var connectionStatus = "Disconnected"
    @Published var winningTicker:   String?          = nil

    // Option positions
    @Published var sellPutPositions:      [OptionPosition] = []
    @Published var creditSpreadPositions: [OptionPosition] = []
    @Published var zeroDTEPositions:      [OptionPosition] = []
    @Published var sellPutStats:          OptionStats?     = nil
    @Published var creditSpreadStats:     OptionStats?     = nil
    @Published var zeroDTEStats:          OptionStats?     = nil
    @Published var winningSellPut:        String?          = nil
    @Published var winningCreditSpread:   String?          = nil
    @Published var winningZeroDTE:        String?          = nil

    private var webSocket:  URLSessionWebSocketTask?
    private var serverURL = UserDefaults.standard.string(forKey: "botServerURL")
        ?? "ws://192.168.1.192:8765/ws/live"

    override init() { super.init() }

    // MARK: - Connection

    func connect(to url: String) {
        serverURL = url
        UserDefaults.standard.set(url, forKey: "botServerURL")
        guard let wsURL = URL(string: url) else {
            connectionStatus = "Invalid URL"; isConnected = false; return
        }
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: .main)
        webSocket = session.webSocketTask(with: wsURL)
        webSocket?.resume()
        connectionStatus = "Connecting..."
        receiveMessages()
    }

    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        isConnected = false
        connectionStatus = "Disconnected"
    }

    // MARK: - Receive

    private func receiveMessages() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let json): self?.handleMessage(json)
                case .data(let data):   self?.handleMessage(String(data: data, encoding: .utf8) ?? "")
                @unknown default: break
                }
                self?.receiveMessages()
            case .failure(let error):
                DispatchQueue.main.async {
                    self?.connectionStatus = "Error: \(error.localizedDescription)"
                    self?.isConnected = false
                }
            }
        }
    }

    private func handleMessage(_ json: String) {
        guard let data = json.data(using: .utf8) else { return }
        do {
            let update = try JSONDecoder().decode(LiveUpdate.self, from: data)
            DispatchQueue.main.async {
                self.botStatus            = update.botStatus
                self.positions            = update.positions
                self.pnlStats             = update.pnl
                self.winningTicker        = update.winningTicker
                self.sellPutPositions      = update.sellPutPositions
                self.creditSpreadPositions = update.creditSpreadPositions
                self.zeroDTEPositions      = update.zeroDTEPositions
                self.sellPutStats          = update.sellPutStats
                self.creditSpreadStats     = update.creditSpreadStats
                self.zeroDTEStats          = update.zeroDTEStats
                self.winningSellPut        = update.winningSellPut
                self.winningCreditSpread   = update.winningCreditSpread
                self.winningZeroDTE        = update.winningZeroDTE
                self.connectionStatus     = "Connected"
                self.isConnected          = true
            }
        } catch {
            print("Decode error: \(error)")
        }
    }

    // MARK: - Commands

    func sendCommand(_ action: String) {
        postControl(["action": action])
    }

    func sendTickers(_ symbols: [String]) {
        postControl(["action": "set_symbols", "symbols": symbols])
    }

    func sendOptionTickers(sellPut: [String], creditSpread: [String]) {
        postControl([
            "action": "set_option_symbols",
            "parameters": ["sell_put": sellPut, "credit_spread": creditSpread]
        ])
    }

    func refresh() async {
        let base = serverURL
            .replacingOccurrences(of: "ws://",  with: "http://")
            .replacingOccurrences(of: "wss://", with: "https://")
            .replacingOccurrences(of: "/ws/live", with: "")
        guard let url = URL(string: base + "/snapshot") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = String(data: data, encoding: .utf8) {
                handleMessage(json)
            }
        } catch {
            print("Refresh error: \(error)")
        }
    }

    private func postControl(_ body: [String: Any]) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: body) else { return }
        let base = serverURL
            .replacingOccurrences(of: "ws://", with: "http://")
            .replacingOccurrences(of: "/ws/live", with: "")
        guard let url = URL(string: base + "/control") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = jsonData
        URLSession.shared.dataTask(with: req).resume()
    }

    // MARK: - URLSessionWebSocketDelegate
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async { self.isConnected = true; self.connectionStatus = "Connected" }
    }
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async { self.isConnected = false; self.connectionStatus = "Disconnected" }
    }
}

// MARK: - Models

struct BotStatus: Codable {
    var isRunning: Bool; var mode: String
    var equity: Double;  var cash: Double
    var dailyPnl: Double; var positions: Int; var tradestoday: Int
    enum CodingKeys: String, CodingKey {
        case isRunning = "is_running"; case mode, equity, cash
        case dailyPnl = "daily_pnl"; case positions; case tradestoday = "trades_today"
    }
}

struct Position: Codable, Identifiable {
    var id: String { symbol }
    var symbol: String; var qty: Double
    var entryPrice: Double; var currentPrice: Double
    var unrealizedPnl: Double; var unrealizedPnlPct: Double
    enum CodingKeys: String, CodingKey {
        case symbol, qty
        case entryPrice = "entry_price"; case currentPrice = "current_price"
        case unrealizedPnl = "unrealized_pnl"; case unrealizedPnlPct = "unrealized_pnl_pct"
    }
}

struct OptionPosition: Codable, Identifiable {
    var id: String { "\(symbol)-\(strategy)-\(strike)-\(expiry)" }
    var symbol: String;   var strategy: String
    var strike: Double;   var upperStrike: Double?
    var expiry: String;   var premiumCollected: Double
    var currentValue: Double; var qty: Int
    var unrealizedPnl: Double; var unrealizedPnlPct: Double
    var daysToExpiry: Int; var delta: Double; var theta: Double
    enum CodingKeys: String, CodingKey {
        case symbol, strategy, strike, expiry, qty, delta, theta
        case upperStrike      = "upper_strike"
        case premiumCollected = "premium_collected"
        case currentValue     = "current_value"
        case unrealizedPnl    = "unrealized_pnl"
        case unrealizedPnlPct = "unrealized_pnl_pct"
        case daysToExpiry     = "days_to_expiry"
    }
}

struct OptionStats: Codable {
    var realizedPnl: Double; var unrealizedPnl: Double
    var totalPnl: Double;    var openPositions: Int; var winRate: Double
    enum CodingKeys: String, CodingKey {
        case realizedPnl   = "realized_pnl";   case unrealizedPnl = "unrealized_pnl"
        case totalPnl      = "total_pnl";      case openPositions = "open_positions"
        case winRate       = "win_rate"
    }
}

struct PnLStats: Codable {
    var realizedPnl: Double; var unrealizedPnl: Double; var totalPnl: Double
    var winningTrades: Int;  var losingTrades: Int;     var totalTrades: Int; var winRatePct: Double
    enum CodingKeys: String, CodingKey {
        case realizedPnl   = "realized_pnl"; case unrealizedPnl = "unrealized_pnl"
        case totalPnl      = "total_pnl";    case winningTrades = "winning_trades"
        case losingTrades  = "losing_trades"; case totalTrades   = "total_trades"
        case winRatePct    = "win_rate_pct"
    }
}

struct LiveUpdate: Codable {
    var timestamp:             String
    var botStatus:             BotStatus
    var positions:             [Position]
    var pnl:                   PnLStats
    var winningTicker:         String?
    var sellPutPositions:      [OptionPosition]
    var creditSpreadPositions: [OptionPosition]
    var zeroDTEPositions:      [OptionPosition]
    var sellPutStats:          OptionStats?
    var creditSpreadStats:     OptionStats?
    var zeroDTEStats:          OptionStats?
    var winningSellPut:        String?
    var winningCreditSpread:   String?
    var winningZeroDTE:        String?
    enum CodingKeys: String, CodingKey {
        case timestamp; case botStatus = "bot_status"
        case positions, pnl
        case winningTicker         = "winning_ticker"
        case sellPutPositions      = "sell_put_positions"
        case creditSpreadPositions = "credit_spread_positions"
        case zeroDTEPositions      = "zero_dte_positions"
        case sellPutStats          = "sell_put_stats"
        case creditSpreadStats     = "credit_spread_stats"
        case zeroDTEStats          = "zero_dte_stats"
        case winningSellPut        = "winning_sell_put"
        case winningCreditSpread   = "winning_credit_spread"
        case winningZeroDTE        = "winning_zero_dte"
    }
}
