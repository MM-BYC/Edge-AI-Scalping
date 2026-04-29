import Foundation

class BotService: NSObject, ObservableObject, URLSessionWebSocketDelegate {
    @Published var isConnected = false
    @Published var botStatus: BotStatus?
    @Published var positions: [Position] = []
    @Published var pnlStats: PnLStats?
    @Published var connectionStatus = "Disconnected"

    private var webSocket: URLSessionWebSocket?
    private var serverURL = UserDefaults.standard.string(forKey: "botServerURL") ?? "ws://192.168.1.192:8765"
    private var receiveTask: URLSessionWebSocketTask?

    override init() {
        super.init()
    }

    func connect(to url: String) {
        serverURL = url
        UserDefaults.standard.set(url, forKey: "botServerURL")

        let wsURL = URL(string: url)!
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: .main)
        webSocket = session.webSocketTask(with: wsURL)
        webSocket?.resume()

        isConnected = true
        connectionStatus = "Connecting..."
        receiveMessages()
    }

    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        isConnected = false
        connectionStatus = "Disconnected"
    }

    private func receiveMessages() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let json):
                    self?.handleMessage(json)
                    self?.receiveMessages()
                case .data(let data):
                    self?.handleData(data)
                    self?.receiveMessages()
                @unknown default:
                    self?.receiveMessages()
                }
            case .failure(let error):
                print("WebSocket error: \(error)")
                self?.connectionStatus = "Disconnected"
                self?.isConnected = false
            }
        }
    }

    private func handleMessage(_ json: String) {
        guard let data = json.data(using: .utf8) else { return }
        let decoder = JSONDecoder()

        do {
            let update = try decoder.decode(LiveUpdate.self, from: data)
            DispatchQueue.main.async {
                self.botStatus = update.botStatus
                self.positions = update.positions
                self.pnlStats = update.pnl
                self.connectionStatus = "Connected"
            }
        } catch {
            print("Failed to decode message: \(error)")
        }
    }

    private func handleData(_ data: Data) {
        handleMessage(String(data: data, encoding: .utf8) ?? "")
    }

    func sendCommand(_ action: String) {
        let command = ["action": action]
        guard let jsonData = try? JSONSerialization.data(withJSONObject: command) else { return }

        let urlRequest = URLRequest(url: URL(string: serverURL.replacingOccurrences(of: "ws://", with: "http://") + "/control")!)
        var request = urlRequest
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData

        URLSession.shared.dataTask(with: request).resume()
    }
}

struct BotStatus: Codable {
    var isRunning: Bool
    var mode: String
    var equity: Double
    var cash: Double
    var dailyPnl: Double
    var positions: Int
    var tradestoday: Int

    enum CodingKeys: String, CodingKey {
        case isRunning = "is_running"
        case mode, equity, cash
        case dailyPnl = "daily_pnl"
        case positions
        case tradestoday = "trades_today"
    }
}

struct Position: Codable, Identifiable {
    var id: String { symbol }
    var symbol: String
    var qty: Double
    var entryPrice: Double
    var currentPrice: Double
    var unrealizedPnl: Double
    var unrealizedPnlPct: Double

    enum CodingKeys: String, CodingKey {
        case symbol, qty
        case entryPrice = "entry_price"
        case currentPrice = "current_price"
        case unrealizedPnl = "unrealized_pnl"
        case unrealizedPnlPct = "unrealized_pnl_pct"
    }
}

struct PnLStats: Codable {
    var realizedPnl: Double
    var unrealizedPnl: Double
    var totalPnl: Double
    var winningTrades: Int
    var losingTrades: Int
    var totalTrades: Int
    var winRatePct: Double

    enum CodingKeys: String, CodingKey {
        case realizedPnl = "realized_pnl"
        case unrealizedPnl = "unrealized_pnl"
        case totalPnl = "total_pnl"
        case winningTrades = "winning_trades"
        case losingTrades = "losing_trades"
        case totalTrades = "total_trades"
        case winRatePct = "win_rate_pct"
    }
}

struct LiveUpdate: Codable {
    var timestamp: String
    var botStatus: BotStatus
    var positions: [Position]
    var pnl: PnLStats

    enum CodingKeys: String, CodingKey {
        case timestamp
        case botStatus = "bot_status"
        case positions, pnl
    }
}
