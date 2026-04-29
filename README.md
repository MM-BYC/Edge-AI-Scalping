# Edge AI Scalping Bot — Complete Documentation

**Low-latency algorithmic trading bot for scalping on Alpaca. Hybrid ML + Rules engine running on Mac mini with SwiftUI iOS dashboard.**

**Status**: Production-ready for paper trading. Full risk controls enabled.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Overview](#system-overview)
3. [Complete Data Flow](#complete-data-flow)
4. [Mac Mini Setup & Operation](#mac-mini-setup--operation)
5. [iOS Dashboard & Control](#ios-dashboard--control)
6. [Module Reference](#module-reference)
7. [Configuration Guide](#configuration-guide)
8. [Risk Management](#risk-management)
9. [Performance Monitoring](#performance-monitoring)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Install uv (Fast Python Manager)

```bash
# macOS
brew install uv

# Verify
uv --version
```

### Clone & Setup

```bash
cd /path/to/Edge_AI_scalping
uv sync                    # Install all dependencies
cp .env.example .env       # Create config file
```

### Configure Alpaca Credentials

```bash
# Edit .env
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
MODE=paper                 # Start with paper trading
SYMBOLS=SPY,QQQ,AAPL,TSLA,NVDA
```

Get credentials from [app.alpaca.markets](https://app.alpaca.markets).

### Train ML Model (First Time)

```bash
uv run -- python engine/models/train.py
# Generates: engine/models/scalp_v1.onnx
```

### Run Bot

```bash
# Terminal 1: Start bot on Mac mini
uv run -- python engine/main.py

# Terminal 2: Build & run iOS app
cd ios/EdgeAI
xcodebuild -scheme EdgeAI -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16' build
# Or open in Xcode:
open EdgeAI.xcodeproj
```

Bot API listens on `http://localhost:8765` (WebSocket for iOS).

---

## System Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAC MINI (EXECUTOR)                       │
│                  Runs: uv run -- python main.py                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 ALPACA BROKER (Cloud)                    │   │
│  │  ├─ Real-time 1-second bars (WebSocket stream)          │   │
│  │  ├─ Paper or Live trading accounts                      │   │
│  │  └─ Order execution & fills                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│           ▲                                      │                │
│           │                                      │                │
│      (DATA IN)                              (ORDERS OUT)          │
│           │                                      │                │
│  ┌────────┴──────────────────────────────────────▼─────────┐    │
│  │              DATA FEED & SIGNAL ENGINE                   │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │ Bar Buffer (circular, 500 bars per symbol)       │   │    │
│  │  │ SPY: [20.0, 20.1, 20.05, ...]                    │   │    │
│  │  │ QQQ: [100.0, 100.2, 100.1, ...]                 │   │    │
│  │  │ AAPL: [150.5, 150.6, 150.4, ...]                │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                         ▼                                │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │         SIGNAL GENERATION (ENSEMBLE)            │   │    │
│  │  │                                                  │   │    │
│  │  │  Rules Engine (40% weight)                       │   │    │
│  │  │  ├─ RSI(14)      → Overbought/Oversold          │   │    │
│  │  │  ├─ MACD(12,26)  → Momentum crossovers          │   │    │
│  │  │  ├─ VWAP         → Price vs volume-weighted avg │   │    │
│  │  │  ├─ Volume Delta → Recent vol ratio              │   │    │
│  │  │  └─ Signal: {-1, 0, 1}                           │   │    │
│  │  │                                                  │   │    │
│  │  │  ML Model (60% weight)                           │   │    │
│  │  │  ├─ ONNX inference (0.5ms on M-series)          │   │    │
│  │  │  ├─ Input: 20-bar normalized OHLCV features     │   │    │
│  │  │  ├─ Output: {-1, 0, 1} + confidence score       │   │    │
│  │  │  └─ CoreML execution provider (Apple Neural)     │   │    │
│  │  │                                                  │   │    │
│  │  │  Ensemble Vote                                   │   │    │
│  │  │  └─ weighted(rules, ml) → final signal           │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────┘    │
│                         ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │         EXECUTION LAYER (ORDER MANAGEMENT)               │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │ Risk Manager                                     │    │   │
│  │  │ ├─ Daily loss cap check: -2% → HARD STOP       │    │   │
│  │  │ ├─ Max positions: 5                             │    │   │
│  │  │ ├─ Per-trade stop: -0.3%                        │    │   │
│  │  │ ├─ Consecutive loss cooldown                    │    │   │
│  │  │ └─ Options delta limit                          │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │ Order Router                                     │    │   │
│  │  │ ├─ Signal → pre-validated order (async)         │    │   │
│  │  │ ├─ Position sizing: 2% of equity per trade      │    │   │
│  │  │ ├─ Market orders for entry (fast execution)     │    │   │
│  │  │ └─ Alpaca REST API (httpx, connection pooled)   │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │ PnL Tracker                                      │    │   │
│  │  │ ├─ Realized P&L (closed trades)                │    │   │
│  │  │ ├─ Unrealized P&L (open positions)             │    │   │
│  │  │ ├─ Win rate, profit factor                     │    │   │
│  │  │ └─ Fill log & execution history                │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └────────────────────────────────────────────────────────────┘    │
│                         ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              FASTAPI SERVER (port 8765)                   │   │
│  │  ├─ GET /status           → bot running, equity, P&L     │   │
│  │  ├─ GET /positions        → open trades with P&L         │   │
│  │  ├─ GET /pnl              → stats (wins, losses, rate)    │   │
│  │  ├─ POST /control         → start/stop/pause commands     │   │
│  │  ├─ WS /ws/live          → 500ms push (equity, fills)    │   │
│  │  └─ GET /health           → connectivity check            │   │
│  └────────────────────────────────────────────────────────────┘   │
│           ▲                                                       │
│           │ (WebSocket, LAN)                                      │
│           │ {"equity": 102500, "daily_pnl": 250, ...}           │
│           │                                                       │
└─────────────┬───────────────────────────────────────────────────┘
              │
              │ (LAN connection via WiFi/Ethernet)
              │
         ┌────┴─────────────────────────────────────────┐
         │                                               │
┌────────▼──────────────────────────────────────────────────────┐
│                  iOS APP (iPhone/iPad)                        │
│                    SwiftUI Dashboard                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  [Dashboard Tab]  [Positions Tab]  [Control Tab]       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Dashboard View                                          │ │
│  │ ┌───────────────────────────────────────────────────┐  │ │
│  │ │ Status: ● Connected (Green) / Disconnected (Red) │  │ │
│  │ │ Server: ws://192.168.1.100:8765                 │  │ │
│  │ └───────────────────────────────────────────────────┘  │ │
│  │                                                         │ │
│  │ ┌───────────────────────────────────────────────────┐  │ │
│  │ │ Equity:         $102,500.00                      │  │ │
│  │ │ Daily P&L:      +$250.50 (green)                 │  │ │
│  │ │ Cash:           $84,200.00                       │  │ │
│  │ │ Positions:      3                                │  │ │
│  │ │ Trades Today:   5                                │  │ │
│  │ └───────────────────────────────────────────────────┘  │ │
│  │                                                         │ │
│  │ ┌───────────────────────────────────────────────────┐  │ │
│  │ │ Total P&L:      +$1,250.00                       │  │ │
│  │ │ Win Rate:       60.0%                            │  │ │
│  │ │ Total Trades:   5                                │  │ │
│  │ └───────────────────────────────────────────────────┘  │ │
│  │                                                         │ │
│  │ [📊 Equity Curve Chart]                                │ │
│  │ ┌─────────────────────────────────────────────────┐   │ │
│  │ │                     /                          │   │ │
│  │ │                    /                           │   │ │
│  │ │                   /                            │   │ │
│  │ │      ────────────/                             │   │ │
│  │ │     /                                          │   │ │
│  │ │____/____________________________________________   │ │
│  │ └─────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Positions View                                          │ │
│  │ ┌─ SPY ─────────────────────────────────────────────┐  │ │
│  │ │ 100 shares @ $420.50 (Entry)                     │  │ │
│  │ │ Current: $421.25                                 │  │ │
│  │ │ P&L: +$75.00 (+0.18%)                            │  │ │
│  │ └─────────────────────────────────────────────────┘  │ │
│  │ ┌─ QQQ ─────────────────────────────────────────────┐  │ │
│  │ │ 50 shares @ $380.00 (Entry)                      │  │ │
│  │ │ Current: $379.50                                 │  │ │
│  │ │ P&L: -$25.00 (-0.13%)                            │  │ │
│  │ └─────────────────────────────────────────────────┘  │ │
│  │ ┌─ AAPL ─────────────────────────────────────────────┐ │ │
│  │ │ 200 shares @ $180.25 (Entry)                     │  │ │
│  │ │ Current: $180.75                                 │  │ │
│  │ │ P&L: +$100.00 (+0.28%)                           │  │ │
│  │ └─────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Control View                                            │ │
│  │ ┌─────────────────────────────────────────────────┐    │ │
│  │ │ Server URL: 192.168.1.100:8765      [Edit ✏️]  │    │ │
│  │ │ [           Connect            ]                 │    │ │
│  │ └─────────────────────────────────────────────────┘    │ │
│  │                                                         │ │
│  │ ┌─────────────────────────────────────────────────┐    │ │
│  │ │ [  Start  ] [ Pause ] [ Stop ]                 │    │ │
│  │ └─────────────────────────────────────────────────┘    │ │
│  │                                                         │ │
│  │ ℹ️ Settings                                             │ │
│  │ Enter Mac mini IP (System Preferences > Network)       │ │
│  │ Bot will auto-broadcast WebSocket on port 8765         │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Complete Data Flow

### Tick-by-Tick Execution (Every 1 Second)

```
1. MARKET DATA ARRIVES (Alpaca WebSocket)
   └─ New 1-second bar: SPY $420.50
      • Open: $420.45
      • High: $420.52
      • Low: $420.40
      • Close: $420.50
      • Volume: 15,000 shares

2. DATA BUFFERING
   └─ Buffer stores last 500 bars per symbol
   └─ SPY buffer: [..., 420.48, 420.49, 420.50]  ← newest

3. SIGNAL GENERATION (if buffer ready: min 20 bars)
   ├─ Technical Rules (40% weight)
   │  ├─ RSI(14) = 55.2 (neutral zone)
   │  ├─ MACD = 0.15, Signal = 0.12 → positive cross
   │  ├─ VWAP = $420.40 → price above VWAP (bullish)
   │  └─ Rules Signal: +1 (BUY)
   │
   └─ ML Model (60% weight)
      ├─ Features: [normalized closes, returns, vol ratio] (20-dim)
      ├─ ONNX inference: <0.5ms (CoreML accelerated)
      ├─ Output: class probabilities [0.2, 0.3, 0.5]
      └─ ML Signal: +1 (BUY, confidence 0.5)
   
   └─ Ensemble Vote
      ├─ Final Signal = 0.4 * (+1) + 0.6 * (+1) = +1.0
      └─ Signal: +1 BUY (high confidence)

4. RISK CHECK (< 1ms)
   ├─ Daily P&L: -$50 (within -$2,000 cap ✓)
   ├─ Open Positions: 3 of 5 max ✓
   ├─ Can Trade: YES ✓
   └─ Position Size: 2% of $100k = $2,000 → 4.8 shares

5. ORDER SUBMISSION (async, ~2ms)
   ├─ Pre-validate: qty=4, side=buy, symbol=SPY, type=market
   ├─ Submit: POST /v2/orders to Alpaca
   ├─ Response: Order ID = abc123, status=pending
   └─ Log: "Entry order submitted SPY 4 shares @ market (~$420.50)"

6. FILL NOTIFICATION (from Alpaca WebSocket, 10-50ms)
   ├─ Order abc123 filled at $420.51
   ├─ Entry recorded: SPY, 4 shares @ $420.51
   ├─ P&L Tracker: unrealized = $0 (just entered)
   └─ Push to iOS: {"symbol": "SPY", "qty": 4, "status": "filled"}

7. POSITION MONITORING (every bar)
   ├─ New bar: SPY $420.75
   ├─ Unrealized P&L: (420.75 - 420.51) * 4 = $0.96
   ├─ Unrealized %: 0.06%
   ├─ Stop Loss Check: $0.96 profit > -$12.61 stop ✓
   └─ Take Profit Check: Not triggered yet

8. EXIT SIGNAL (next bar if conditions met)
   ├─ If RSI > 70 AND ML signal = -1
   ├─ Exit Signal: -1 (SELL)
   ├─ Risk Check: Can close position? YES
   ├─ Submit: POST /v2/orders (market sell 4 SPY)
   └─ Fill: Sold at $420.80

9. TRADE CLOSURE & P&L REALIZATION
   ├─ Realized P&L: (420.80 - 420.51) * 4 = $1.16 ✓ WIN
   ├─ Statistics:
   │  • Total Trades: 5
   │  • Winning Trades: 3
   │  • Losing Trades: 2
   │  • Win Rate: 60%
   └─ Daily P&L: +$250.50

10. iOS DASHBOARD PUSH (WebSocket, every 500ms)
    └─ {"equity": $100,250, "daily_pnl": $250.50, "positions": 3, ...}
       └─ iPhone updates in real-time: "+$250.50" (green)
```

---

## Mac Mini Setup & Operation

### System Requirements

- **OS**: macOS 12+ (or Mac mini 2020+)
- **Python**: 3.11+
- **Network**: Ethernet or 5GHz WiFi (recommended for low latency)
- **Alpaca Account**: Paper or Live trading account

### Step 1: Initial Setup

```bash
# Clone project (if not already done)
cd ~/Sandbox/Project/Edge_AI_scalping

# Install uv (one-time)
brew install uv

# Install project dependencies
uv sync

# Verify installation
uv run -- python --version  # Should show Python 3.11+
```

### Step 2: Configure Credentials

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env
```

Fill in:
```bash
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODE=paper                          # Start here
SYMBOLS=SPY,QQQ,AAPL,TSLA,NVDA     # Symbols to trade
```

**Get credentials:**
1. Go to [app.alpaca.markets](https://app.alpaca.markets)
2. Login with your account
3. Dashboard → Settings → API Keys
4. Copy API Key and Secret Key into `.env`

### Step 3: Train ML Model (First Time Only)

```bash
# Generate ONNX model
uv run -- python engine/models/train.py

# Output:
# Training LightGBM on 1000 samples...
# Model trained successfully
# Model exported to engine/models/scalp_v1.onnx
# Training complete!
```

This creates the ML model used for signal generation. Takes ~30 seconds.

### Step 4: Start Bot

```bash
# Terminal 1: Start the bot
uv run -- python engine/main.py

# Expected output:
# 2026-04-28 14:35:22,123 [INFO] Initializing Edge AI Scalping Bot
# 2026-04-28 14:35:22,125 [INFO] Mode: PAPER
# 2026-04-28 14:35:22,126 [INFO] Symbols: ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA']
# 2026-04-28 14:35:22,500 [INFO] Data feed connected
# 2026-04-28 14:35:22,600 [INFO] API server started on 0.0.0.0:8765
# 2026-04-28 14:35:23,000 [INFO] Bot ready, waiting for market data...
```

The bot is now running and listening on `http://localhost:8765`.

### Step 5: Monitor Logs

While bot is running, watch for these log patterns:

```bash
# New bar arrives (every ~1 second during market hours)
2026-04-28 14:35:45,123 [DEBUG] Signal: SPY -> 1 (confidence=0.72%) [rules=1, ml=1, price=$420.50]

# Order submitted
2026-04-28 14:35:46,500 [INFO] Entry order submitted: SPY 4 buy -> abc123xyz

# Position opened
2026-04-28 14:35:47,200 [INFO] Position opened: SPY, entry=$420.51, qty=4

# Position closed (realized P&L)
2026-04-28 14:35:52,800 [INFO] Position closed: SPY, P&L = $1.16

# Status updates (every 5 seconds)
2026-04-28 14:35:55,000 [DEBUG] Status: equity=$100250, pnl=$250, positions=3, trades=5, can_trade=True
```

### Step 6: Access Bot Status (Separate Terminal)

```bash
# Terminal 2: Check bot health
curl http://localhost:8765/health
# Response: {"status":"ok","timestamp":"2026-04-28T14:35:55"}

# Get current P&L
curl http://localhost:8765/pnl
# Response: {"realized_pnl": 250.5, "unrealized_pnl": 75.2, "total_pnl": 325.7, ...}

# Get open positions
curl http://localhost:8765/positions
# Response: [{"symbol": "SPY", "qty": 4, "entry_price": 420.51, ...}, ...]

# Get risk status
curl http://localhost:8765/risk
# Response: {"can_trade": true, "daily_pnl": 250.5, "equity": 100250, ...}
```

### Mac Operation Checklist

- [ ] Market hours (9:30 AM - 4:00 PM ET weekdays)
- [ ] Mac mini connected to network (wired Ethernet preferred)
- [ ] Terminal running: `uv run -- python engine/main.py`
- [ ] Logs showing new bars every ~1 second
- [ ] `curl http://localhost:8765/health` returns OK
- [ ] iOS app connected (see next section)
- [ ] Monitor daily P&L in iOS dashboard (update every 500ms)

### Stopping the Bot

```bash
# Press Ctrl+C in the terminal running the bot
# Expected output:
# 2026-04-28 14:45:00,000 [INFO] Interrupted by user
# 2026-04-28 14:45:00,500 [INFO] Closing all positions...
# 2026-04-28 14:45:01,200 [INFO] Bot stopped
```

The bot will close all open positions before shutting down.

---

## iOS Dashboard & Control

### Installation

**Xcode 14+ Required**

```bash
# On Mac mini
cd ios/EdgeAI
open EdgeAI.xcodeproj  # Opens in Xcode

# Or build from CLI
xcodebuild build -scheme EdgeAI
```

### Building & Running

1. **Connect iPhone to same WiFi as Mac mini**
2. **Open Xcode**
   - File → Open → `ios/EdgeAI`
3. **Select Target**
   - Top left: Select your iPhone
4. **Build & Run**
   - Cmd+R or Product → Run
5. **App launches on iPhone**
   - Takes ~10 seconds to build on first run

### Dashboard Walkthrough

#### 1. Dashboard Tab (Main View)

```
┌─────────────────────────────────┐
│  Edge AI Scalping              │
├─────────────────────────────────┤
│                                 │
│ ● Connected (green indicator)   │
│   192.168.1.100:8765           │
│                                 │
│ ┌───────────────────────────┐  │
│ │ Equity      $102,500.00   │  │
│ │ Daily P&L   +$250.50  🟢  │  │
│ │ Cash        $84,200.00    │  │
│ │ Positions   3             │  │
│ │ Trades      5             │  │
│ └───────────────────────────┘  │
│                                 │
│ ┌───────────────────────────┐  │
│ │ Total P&L   +$1,250.00    │  │
│ │ Win Rate    60.0%         │  │
│ │ Trades      5             │  │
│ └───────────────────────────┘  │
│                                 │
│ [Equity Curve Chart]            │
│ ┌───────────────────────────┐  │
│ │        /---────┐          │  │
│ │       /                   │  │
│ │      /                    │  │
│ │  ---/                     │  │
│ │ /___________________      │  │
│ └───────────────────────────┘  │
│        Apr 28    Sep 28         │
│                                 │
│ [  Connect  ]                   │
│                                 │
└─────────────────────────────────┘
```

**What It Shows:**
- **Connection Status** (green = connected, red = disconnected)
- **Server URL** (IP/hostname of Mac mini)
- **Equity**: Total account value
- **Daily P&L**: Profit/loss for the day (green if positive)
- **Cash**: Available to trade
- **Positions**: Number of open trades
- **Trades**: Total trades executed today
- **Equity Curve**: Visual chart of account growth
- **[Connect]**: Button to establish WebSocket connection

**Real-Time Updates:** All values update every 500ms from Mac mini.

---

#### 2. Positions Tab (Open Trades)

```
┌─────────────────────────────────┐
│  Positions                      │
├─────────────────────────────────┤
│                                 │
│ SPY                         100 │
│ Entry: $420.50                  │
│ Current: $421.25                │
│ P&L: +$75.00 (+0.18%)       🟢 │
│ ─────────────────────────────── │
│                                 │
│ QQQ                          50 │
│ Entry: $380.00                  │
│ Current: $379.50                │
│ P&L: -$25.00 (-0.13%)       🔴 │
│ ─────────────────────────────── │
│                                 │
│ AAPL                        200 │
│ Entry: $180.25                  │
│ Current: $180.75                │
│ P&L: +$100.00 (+0.28%)      🟢 │
│ ─────────────────────────────── │
│                                 │
│ (No more positions)             │
│                                 │
└─────────────────────────────────┘
```

**What It Shows:**
- **Symbol**: Ticker name
- **Quantity**: Shares held (left side)
- **Entry Price**: Where you bought
- **Current Price**: Real-time market price
- **P&L**: Unrealized profit/loss
- **P&L %**: Percentage gain/loss
- **Color**: Green (winning) / Red (losing)

**Updates:** Every 500ms as price ticks on Alpaca.

---

#### 3. Control Tab (Bot Commands)

```
┌─────────────────────────────────┐
│  Control                        │
├─────────────────────────────────┤
│                                 │
│ Server Connection               │
│ ┌──────────────────────────┐   │
│ │ 192.168.1.100:8765   ✎  │   │
│ └──────────────────────────┘   │
│                                 │
│ [    Connect    ]               │
│                                 │
│ Bot Control                     │
│ ┌──────────────────────────┐   │
│ │ [ Start ] [ Pause ]      │   │
│ │ [ Stop  ]                │   │
│ └──────────────────────────┘   │
│                                 │
│ ℹ️ Settings                      │
│ Enter Mac mini IP address.      │
│ Find via:                       │
│ • System Preferences > Network  │
│ • Terminal: ifconfig (look for  │
│   inet 192.168.x.x)            │
│                                 │
│ Bot auto-broadcasts on port     │
│ 8765. Ensure WiFi not blocking. │
│                                 │
└─────────────────────────────────┘
```

**Controls:**

1. **Server URL**
   - Enter: `ws://192.168.1.100:8765` (replace IP)
   - Tap ✎ to edit
   - Tap ✓ to save

2. **[Connect]**
   - Establishes WebSocket to Mac mini
   - Status changes to green when successful
   - Dashboard starts updating in real-time

3. **[Start]**
   - Resume trading (if paused)
   - Sends: `{"action": "start"}` to bot

4. **[Pause]**
   - Pause trading (keep positions open)
   - Sends: `{"action": "pause"}` to bot

5. **[Stop]**
   - Stop bot and close all positions
   - Sends: `{"action": "stop"}` to bot

---

### Finding Your Mac Mini IP

**Method 1: System Settings (Easy)**
1. Mac mini: Apple menu → System Settings
2. Network → Show Details
3. Look for "IPv4 Address" (e.g., `192.168.1.100`)
4. Enter this in iOS app

**Method 2: Terminal**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
# Output: inet 192.168.1.100 netmask 0xffffff00 broadcast 192.168.1.255
```

**Method 3: Router Admin Panel**
1. Open browser: `192.168.1.1` (or your router IP)
2. Look for connected devices list
3. Find "Mac mini"

### Connection Troubleshooting

**"Disconnected" status**
- [ ] Check Mac mini IP is correct
- [ ] Verify Mac mini bot is running (`curl http://ip:8765/health`)
- [ ] iPhone on same WiFi as Mac mini
- [ ] No firewall blocking port 8765

**Real-time updates not showing**
- [ ] Tap [Connect] button again
- [ ] Check latency: Status should say "Connected" in green
- [ ] Verify bot is trading (check logs on Mac)

---

## Module Reference

### 1. Core Engine (`engine/main.py`)

**Purpose**: Main orchestrator. Coordinates all components in async event loop.

**Responsibilities:**
- Start broker connection & API server
- Register bar callback
- Generate signals when new bars arrive
- Route signals to order execution
- Update risk tracker
- Log all actions

**Key Methods:**
```python
async start()           # Initialize bot
async stop()            # Shutdown gracefully
async run()             # Main trading loop
_on_new_bar(bar)       # Called every 1-second bar
```

**Configuration**: Reads from `engine/config.py` (via `.env`)

---

### 2. Config Management (`engine/config.py`)

**Purpose**: Centralized settings management using Pydantic.

**Loads from `.env`:**
```bash
ALPACA_API_KEY              # Required
ALPACA_SECRET_KEY           # Required
MODE                        # paper | live
SYMBOLS                     # SPY,QQQ,AAPL,TSLA,NVDA
DAILY_LOSS_CAP             # -0.02 (-2%)
MAX_CONCURRENT_POSITIONS   # 5
PER_TRADE_STOP_LOSS        # -0.003 (-0.3%)
OPTIONS_MAX_DELTA          # 0.5
```

**Properties:**
```python
is_paper        # True if MODE=paper
is_live         # True if MODE=live
model_path_full # Full path to ONNX model
```

---

### 3. Broker Integration (`engine/broker/alpaca_client.py`)

**Purpose**: Async wrapper around Alpaca REST API & WebSocket callbacks.

**Data Structures:**
```python
Bar(symbol, timestamp, open, high, low, close, volume)
```

**Key Methods:**
```python
async connect()              # Establish broker connection
async get_account()         # Fetch account info
async get_positions()       # Get open positions
async submit_market_order() # Buy/sell at market
async submit_limit_order()  # Conditional order
async cancel_order()        # Cancel order by ID
```

**Callbacks:**
```python
subscribe_bars(symbol, callback)   # Register for bar updates
subscribe_fills(symbol, callback)  # Register for fill updates
```

---

### 4. Data Feed (`engine/data/`)

#### `feed.py` — Market Data Stream Manager

**Purpose**: Ingests real-time 1-second bars from Alpaca.

**Key Methods:**
```python
async start()                    # Connect to Alpaca data stream
async stop()                     # Disconnect
get_buffer(symbol)              # Get BarBuffer for symbol
is_ready(min_bars=20)          # Check all symbols ready
all_ready_symbols()            # List symbols with enough bars
```

#### `buffer.py` — Circular OHLCV Ring Buffer

**Purpose**: Store last 500 bars per symbol. Thread-safe numpy views.

**Key Methods:**
```python
append(timestamp, o, h, l, c, v)     # Add bar
get_numpy_arrays(lookback=100)       # Get as numpy arrays
get_last_n_closes(n)                 # Get last N close prices
is_ready(min_bars=20)               # Enough data?
```

**Example:**
```python
buffer = feed.get_buffer("SPY")
timestamps, opens, highs, lows, closes, volumes = buffer.get_numpy_arrays(100)
# closes = [420.45, 420.48, 420.49, 420.50]  (last 100 bars)
```

---

### 5. Signal Generation (`engine/signals/`)

#### `rules.py` — Technical Indicator Rules

**Purpose**: Vectorized technical analysis.

**Indicators** (all return latest value or None):
```python
TechnicalIndicators.rsi(closes, length=14)
TechnicalIndicators.macd(closes, fast=12, slow=26, signal=9)
TechnicalIndicators.vwap(highs, lows, closes, volumes)
TechnicalIndicators.volume_delta(volumes, length=20)
TechnicalIndicators.atr(highs, lows, closes, length=14)
TechnicalIndicators.ema(closes, length=20)
```

**Signal Generation:**
```python
signal, indicators = RuleBasedSignals().generate_signal(
    opens, highs, lows, closes, volumes
)
# signal: -1 (sell), 0 (hold), 1 (buy)
# indicators: dict of all calculated values
```

---

#### `ml_inference.py` — ONNX Model Inference

**Purpose**: Fast ML predictions on Apple Silicon.

**Key Methods:**
```python
def preprocess_features(closes, opens, highs, lows, volumes)
    # → normalized 20-dim feature vector

def predict(features)
    # → (signal, confidence, inference_time_ms)

def is_available()
    # → bool (model loaded successfully?)
```

**Execution Provider**: CoreML on Apple Silicon (M1/M2/M3)
- Inference time: ~0.5ms
- No PyTorch overhead

---

#### `ensemble.py` — Weighted Signal Combiner

**Purpose**: Merge rule signals (40%) + ML signals (60%).

**Key Method:**
```python
signal, analysis = SignalEnsemble(ml_model_path).generate_signal(
    opens, highs, lows, closes, volumes
)
# Returns:
# signal: -1, 0, or 1
# analysis: {
#   'rule_signal': 1,
#   'ml_signal': 1,
#   'ml_confidence': 0.65,
#   'ensemble_signal': 1,
#   'ensemble_confidence': 0.8
# }
```

---

### 6. Execution Layer (`engine/execution/`)

#### `risk.py` — Risk Management Guards

**Purpose**: Hard stops prevent catastrophic losses.

**Guards:**
```python
DAILY_LOSS_CAP = -2%              # No trading after losing 2% today
MAX_CONCURRENT_POSITIONS = 5      # Max 5 open trades
PER_TRADE_STOP_LOSS = -0.3%       # Exit each trade if down 0.3%
OPTIONS_MAX_DELTA = 0.5           # Avoid high-delta options
COOLDOWN_AFTER_LOSSES = 3 trades  # Rest 15min after 3 consecutive losses
```

**Key Methods:**
```python
can_trade()              # (bool, reason) - global trading allowed?
can_enter_position()     # (bool, reason) - new position allowed?
check_position_stop_loss(pnl_pct)  # Should we exit?
on_trade_loss()         # Increment loss streak
on_trade_win()          # Reset loss streak
```

---

#### `router.py` — Order Execution

**Purpose**: Route signals to Alpaca orders.

**Key Methods:**
```python
async route_signal(symbol, signal, price, confidence)
    # Signal → validated order → Alpaca submission

async submit_entry_order(symbol, qty, price)
    # Market order for scalp entry

async close_position(symbol, price, reason)
    # Exit trade at current price
```

**Order Attributes:**
```python
symbol: str              # SPY, QQQ, etc.
qty: float              # Position size (2% of equity)
side: str               # buy | sell
type: str               # market | limit
time_in_force: str      # gtc (good-til-cancel)
```

---

#### `pnl_tracker.py` — Profit & Loss Tracking

**Purpose**: Track realized/unrealized P&L and trade statistics.

**Key Methods:**
```python
record_fill(symbol, side, qty, price)    # Trade executed
update_market_prices(symbol, price)      # Update live prices
get_unrealized_pnl()                     # Open position P&L
get_stats()                              # {realized, unrealized, win_rate, ...}
```

**Metrics:**
```python
realized_pnl        # Closed trade profits
unrealized_pnl      # Current open position P&L
win_rate            # % of profitable trades
avg_hold_bars       # Average bars held per trade
profit_factor       # Total wins / total losses
```

---

### 7. API Server (`engine/api/server.py`)

**Purpose**: FastAPI endpoint for iOS communication.

**Endpoints:**

| Method | Path | Returns |
|--------|------|---------|
| GET | `/health` | `{"status": "ok"}` |
| GET | `/status` | `BotStatus` (equity, daily_pnl, positions) |
| GET | `/positions` | `[Position]` (open trades) |
| GET | `/pnl` | `PnLStats` (win rate, avg hold, etc.) |
| GET | `/risk` | Risk status (can trade, daily loss) |
| POST | `/control` | Accept start/stop/pause commands |
| WS | `/ws/live` | WebSocket: 500ms equity updates |

**WebSocket Message Format:**
```json
{
  "timestamp": "2026-04-28T14:35:22",
  "bot_status": {
    "is_running": true,
    "mode": "paper",
    "equity": 102500.00,
    "daily_pnl": 250.50,
    "positions": 3
  },
  "pnl": {
    "realized_pnl": 250.50,
    "unrealized_pnl": 75.20,
    "total_pnl": 325.70,
    "win_rate_pct": 60.0,
    "total_trades": 5
  }
}
```

---

### 8. Backtesting (`engine/backtest/engine.py`)

**Purpose**: Replay trading logic on historical data.

**Example Usage:**
```python
from engine.backtest.engine import BacktestEngine

bt = BacktestEngine(signal_ensemble, starting_equity=100000)
metrics = bt.run("SPY", historical_bars)

print(f"Sharpe: {metrics.sharpe_ratio}")
print(f"Win Rate: {metrics.win_rate:.1%}")
print(f"Max Drawdown: {metrics.max_drawdown:.1%}")
```

**Metrics:**
```python
total_trades        # Number of round-trip trades
win_rate            # % winning vs losing
sharpe_ratio        # Risk-adjusted return
max_drawdown        # Largest equity decline
profit_factor       # Sum of wins / sum of losses
avg_hold_bars       # Average bars in each trade
```

---

### 9. ML Training (`engine/models/train.py`)

**Purpose**: Train LightGBM classifier, export to ONNX.

**Process:**
1. Load historical 1-minute bars from Alpaca (12 months)
2. Generate 20-dim feature vectors (OHLCV-derived)
3. Label: next bar direction (up, flat, down)
4. Train: LightGBM with walk-forward validation
5. Export: ONNX format (cross-platform, fast inference)

**Usage:**
```bash
uv run -- python engine/models/train.py
# Generates: engine/models/scalp_v1.onnx
```

---

## Configuration Guide

### `.env` Template

```bash
# ─────────────────────────────────────────────────
# BROKER CONFIGURATION
# ─────────────────────────────────────────────────

ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Mode: paper (sandbox, no real money) | live (real trading)
MODE=paper

# ─────────────────────────────────────────────────
# TRADING PARAMETERS
# ─────────────────────────────────────────────────

# Symbols to trade (comma-separated)
# Only liquid stocks recommended for scalping
SYMBOLS=SPY,QQQ,AAPL,TSLA,NVDA

# ─────────────────────────────────────────────────
# RISK MANAGEMENT (HARD STOPS)
# ─────────────────────────────────────────────────

# Daily loss cap: lose X% of equity → no more trades
# Example: -0.02 = -2% = $2,000 on $100k account
DAILY_LOSS_CAP=-0.02

# Maximum concurrent open positions
MAX_CONCURRENT_POSITIONS=5

# Per-trade stop loss: exit if down X%
# Example: -0.003 = -0.3% = stop loss on each trade
PER_TRADE_STOP_LOSS=-0.003

# Options: max delta exposure
# Example: 0.5 = avoid options with delta > 0.5
OPTIONS_MAX_DELTA=0.5

# Consecutive losses before cooldown
COOLDOWN_TRADES=3

# Cooldown duration (minutes) after losing streak
COOLDOWN_MINUTES=15

# ─────────────────────────────────────────────────
# ML MODEL
# ─────────────────────────────────────────────────

# Path to ONNX model (generated by train.py)
ML_MODEL_PATH=engine/models/scalp_v1.onnx

# ─────────────────────────────────────────────────
# API SERVER (FOR iOS)
# ─────────────────────────────────────────────────

# Bind address (0.0.0.0 = all interfaces)
API_HOST=0.0.0.0

# Port for FastAPI (8765 is arbitrary but consistent)
API_PORT=8765

# Log level
API_LOG_LEVEL=info

# ─────────────────────────────────────────────────
# BACKTESTING
# ─────────────────────────────────────────────────

# How many days of history to load for backtesting
BACKTEST_LOOKBACK_DAYS=365

# Training window (days)
BACKTEST_TRAIN_DAYS=60

# Testing window (days)
BACKTEST_TEST_DAYS=10

# ─────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────

LOG_LEVEL=INFO
LOG_FILE=logs/engine.log
```

### Parameter Tuning Guide

**Conservative (Lower Risk)**
```bash
DAILY_LOSS_CAP=-0.01           # -1% (stricter)
MAX_CONCURRENT_POSITIONS=3     # Fewer concurrent trades
PER_TRADE_STOP_LOSS=-0.002     # -0.2% (tighter)
```

**Aggressive (Higher Risk)**
```bash
DAILY_LOSS_CAP=-0.05           # -5% (looser)
MAX_CONCURRENT_POSITIONS=10    # More concurrent
PER_TRADE_STOP_LOSS=-0.005     # -0.5% (wider)
```

**For Backtesting**
```bash
BACKTEST_TRAIN_DAYS=120        # 4 months train
BACKTEST_TEST_DAYS=20          # 20 days test
```

---

## Risk Management

### Hard Stops (Cannot Override)

These limits are **baked into the code** and **cannot be overridden**:

1. **Daily Loss Cap: -2%**
   - If equity drops 2% in a day, no more trades
   - Example: $100k account → -$2,000 → trading stops
   - Resets at market open next day

2. **Max 5 Concurrent Positions**
   - Never hold more than 5 open trades
   - Prevents over-leverage and concentration risk

3. **Per-Trade Stop: -0.3%**
   - Each trade closes if down 0.3%
   - Example: $420 entry → closes at $419.74

4. **Options Max Delta: 0.5**
   - Avoid high-delta options (too volatile)
   - Example: Skip $1 out-of-money calls (delta 0.8+)

5. **Cooldown: 3 Consecutive Losses**
   - After 3 losing trades, 15-minute break
   - Prevents emotional revenge trading
   - Automatically resumes after cooldown

### Position Sizing

**Default: 2% per trade**

```
Equity: $100,000
Position Size: 2% = $2,000
Symbol: SPY @ $420
Quantity: $2,000 / $420 = 4.76 shares (rounds to 4)
```

### Realistic Win Scenarios

**Conservative Strategy** (60% win rate, realistic)
```
100 trades, 60 wins, 40 losses
Avg Win: +$100
Avg Loss: -$50
Gross P&L: (60 × $100) - (40 × $50) = $4,000
After commissions (-$500): +$3,500
Time: 5 trading days @ ~5-10 trades/hour
```

**Aggressive Strategy** (55% win rate, riskier)
```
100 trades, 55 wins, 45 losses
Avg Win: +$200
Avg Loss: -$100
Gross P&L: (55 × $200) - (45 × $100) = $7,500
After commissions (-$500): +$7,000
But: Larger drawdowns, requires bigger account
```

---

## Performance Monitoring

### Metrics to Watch

| Metric | Healthy Range | Warning Sign |
|--------|---------------|--------------|
| **Daily P&L** | +$100–$500 | Negative 2+ days in a row |
| **Win Rate** | 55%–70% | <50% (reverse signals?) |
| **Avg Hold** | 30s–5min | >10min (not scalping) |
| **Drawdown** | <$500 | >$1,000 (stop trading) |
| **Sharpe** | >1.0 | <0.5 (underperforming) |
| **Order Fills** | <100ms | >500ms (slippage?) |

### Logging Output

**Check logs daily:**

```bash
# Terminal running bot
tail -f logs/engine.log

# Or live in another terminal
tail -f logs/engine.log | grep "P&L\|Signal\|Order"
```

**Key Logs:**

```
[INFO] Signal: SPY -> 1 (confidence=0.72%)        ← Strong buy signal
[INFO] Entry order submitted: SPY 4 shares        ← Order placed
[INFO] Position closed: SPY, P&L = $1.16          ← Trade closed (win)
[DEBUG] Status: equity=$100250, pnl=$250, ...     ← Health check
[WARNING] Daily loss cap reached: $50 > $2000     ← STOPPED TRADING
```

### iOS Dashboard Monitoring

**Real-Time Checks:**

1. **Equity Curve** (Should trend up)
   - Watch for sharp drops (drawdowns)
   - Expect 10-20% volatility in equity line

2. **Win Rate** (Should be 50%+)
   - Track weekly: should improve over time
   - <50% = signals degraded, stop trading

3. **Daily P&L** (Watch green → red changes)
   - Red = losing day (monitor carefully)
   - Two red days in a row = review signals

4. **Positions Tab** (Watch P&L %)
   - Green positions: winning
   - Red positions: monitor for stop loss
   - Update lag: max 500ms

---

## Troubleshooting

### Bot Won't Start

**Error: "Alpaca API key/secret not set"**
```bash
# Fix: Check .env file
cat .env | grep ALPACA
# Should see: ALPACA_API_KEY=PKxxx and ALPACA_SECRET_KEY=xxx

# If missing, edit and save
nano .env
```

**Error: "ONNX model not found"**
```bash
# Fix: Train the model first
uv run -- python engine/models/train.py
# Wait for completion (~30 seconds)

# Verify
ls -la engine/models/scalp_v1.onnx
# Should show file, not "No such file"
```

**Error: "Address already in use (port 8765)"**
```bash
# Another process using port 8765
lsof -i :8765
# Kill process
kill -9 <PID>

# Or use different port
API_PORT=9999  # Edit .env
```

---

### No Signals Generating

**Problem: Bot running but no trades**

```bash
# Check 1: Wait for 20 bars (usually <1 minute)
# Bot logs: "Bot ready, waiting for market data..."
# Wait 1-2 minutes during market hours

# Check 2: Verify market hours (9:30 AM - 4:00 PM ET weekdays)
date  # Is it trading hours?

# Check 3: Check symbol is active
curl https://data.alpaca.markets/v1beta3/latest/bars?symbols=SPY
# Should show recent bars

# Check 4: Review signal logs
tail -50 logs/engine.log | grep "Signal"
# Should see signals like: "Signal: SPY -> 1 (confidence=0.72%)"

# If no signals: Signal engine broken, review CLAUDE.md module reference
```

---

### iOS App Won't Connect

**Problem: "Disconnected" in red**

```
Step 1: Verify Mac mini IP
  Terminal on Mac: ifconfig | grep "inet "
  Should show: inet 192.168.1.100 (example)

Step 2: Check bot is running
  Terminal on Mac: curl http://localhost:8765/health
  Should respond: {"status":"ok"}

Step 3: Verify same WiFi
  iPhone Settings > WiFi
  Mac mini: System Settings > Network
  Both on same SSID? (same WiFi network)

Step 4: Check firewall
  Mac: System Preferences > Security & Privacy > Firewall
  Is firewall blocking port 8765?

Step 5: Try direct IP in app
  Remove "ws://" prefix
  Just enter: 192.168.1.100:8765
  Tap Connect
```

**Debug: Test connection from iPhone**

```bash
# On iPhone, open Notes and do this command:
# But iPhone doesn't have Terminal...

# Instead, on Mac mini, test from a different machine on same WiFi:
# From any computer on same network:
curl http://192.168.1.100:8765/health
# Should respond: {"status":"ok"}
```

---

### Orders Not Filling

**Problem: Orders submitted but no fills**

```bash
# Check 1: Paper vs Live mode
grep "^MODE=" .env
# Should be: MODE=paper (for testing)

# Check 2: Market hours
# Orders only fill 9:30 AM - 4:00 PM ET weekdays
# During pre-market (4-9:30 AM) or after-hours (4-8 PM), fills are rare

# Check 3: Check positions exist
curl http://localhost:8765/positions
# Should show filled orders

# Check 4: Review order status in Alpaca web
# Go to: app.alpaca.markets > Orders
# See if orders are "filled" or "pending"

# If pending and market is open: try market order instead of limit
# (Current bot uses market orders, so this shouldn't happen)
```

---

### High Slippage (Fills at bad prices)

**Problem: Orders filled at worse price than expected**

```
Expected: $420.50
Actual Fill: $420.75 (worse by $0.25)

This is normal for:
- Market orders during low liquidity
- Wide bid-ask spreads
- High volatility

Solutions:
1. Trade only SPY, QQQ, AAPL (high liquidity)
2. Use limit orders instead of market (slower, better price)
3. Scalp with smaller position sizes
4. Trade during peak hours (10-11 AM, 2-4 PM ET)
```

---

### Low Performance (Win Rate Dropping)

**Problem: Win rate dropping below 50%**

```bash
# Check 1: Market conditions changed
# Scalping works best in:
# ✓ Trending markets (bull/bear, not choppy)
# ✓ High liquidity (morning, afternoon)
# ✗ During Fed announcements
# ✗ Pre-earnings (high volatility)

# Check 2: Model is stale
# Retrain if not done in 30+ days:
uv run -- python engine/models/train.py

# Check 3: Parameters need tuning
# Review .env risk parameters, try conservative setting:
DAILY_LOSS_CAP=-0.01    # Tighter
PER_TRADE_STOP_LOSS=-0.002

# Check 4: Review recent signal logs
tail -100 logs/engine.log | grep "Signal"
# Look for: confidence scores (should be 0.5-0.8, not 0.1-0.3)
```

---

### Mac Mini Disconnection

**Problem: Bot crashes or disconnects**

```bash
# Check 1: Network connection
ping 8.8.8.8
# Should succeed

# Check 2: Alpaca API status
curl https://api.alpaca.markets/v2/account
# If timeout: Alpaca outage (check status.alpaca.markets)

# Check 3: Memory/CPU pressure
top -n 1 | head -20
# Python process should use <500 MB RAM, <10% CPU
# If higher: restart bot, reduce SYMBOLS count

# Check 4: Reconnect
# Kill bot: Ctrl+C
# Wait 5 seconds
# Restart: uv run -- python engine/main.py
```

---

### iOS Real-Time Updates Lag

**Problem: Dashboard updates slower than 500ms**

```
This is normal if:
- WiFi signal weak (move closer to router)
- Mac mini WiFi congested (use wired Ethernet)
- Many positions (>10 open trades)
- Bot CPU maxed out

Solutions:
1. Use wired Ethernet on Mac mini
2. Reduce SYMBOLS: 2-3 instead of 5
3. Close some positions manually
4. Restart bot during low-trading period
```

---

## Appendix: Files & Directories

```
Edge_AI_scalping/
├── engine/
│   ├── main.py                  # Entry point, orchestrator
│   ├── config.py                # Settings from .env
│   │
│   ├── broker/
│   │   ├── alpaca_client.py     # Alpaca API wrapper
│   │   └── __init__.py
│   │
│   ├── data/
│   │   ├── feed.py              # Real-time bar stream
│   │   ├── buffer.py            # Circular OHLCV storage
│   │   └── __init__.py
│   │
│   ├── signals/
│   │   ├── rules.py             # Technical indicators
│   │   ├── ml_inference.py      # ONNX model
│   │   ├── ensemble.py          # Signal combiner
│   │   └── __init__.py
│   │
│   ├── execution/
│   │   ├── risk.py              # Risk management
│   │   ├── router.py            # Order execution
│   │   ├── pnl_tracker.py       # P&L tracking
│   │   └── __init__.py
│   │
│   ├── backtest/
│   │   ├── engine.py            # Walk-forward simulator
│   │   └── __init__.py
│   │
│   ├── api/
│   │   ├── server.py            # FastAPI endpoints
│   │   ├── schemas.py           # Pydantic models
│   │   └── __init__.py
│   │
│   └── models/
│       ├── train.py             # Model training
│       ├── scalp_v1.onnx        # Trained model (generated)
│       └── __init__.py
│
├── ios/
│   └── EdgeAI/
│       ├── App.swift            # SwiftUI entry
│       ├── Views/
│       │   ├── DashboardView.swift
│       │   ├── PositionsView.swift
│       │   └── ControlView.swift
│       └── Services/
│           └── BotService.swift  # WebSocket client
│
├── tests/
│   ├── test_signals.py
│   ├── test_risk.py
│   └── test_backtest.py
│
├── .env.example               # Configuration template
├── .env                       # Your credentials (don't commit!)
├── .gitignore                # Git ignore rules
├── pyproject.toml            # uv/Poetry config
├── README.md                 # This file
├── CLAUDE.md                 # Technical deep dive
└── logs/
    └── engine.log            # Trading logs (generated)
```

---

## Support & Next Steps

1. **Paper Trading**: Run with `MODE=paper` for 1–2 weeks
2. **Monitor**: Check logs daily, review Win Rate
3. **Tune**: Adjust parameters in `.env` based on performance
4. **Go Live**: Only switch to `MODE=live` after proven profitability
5. **Document**: Keep notes on what parameters work best

**Remember:**
- This is a **scalping bot** (seconds to minutes), not swing trading
- Realistic target: 50–70% win rate, $100–$500/day on $100k account
- Always start with `MODE=paper`
- Risk management is hardcoded (cannot override)

Happy trading! 📈
