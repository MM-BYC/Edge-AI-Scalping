# Edge AI Scalping Bot

Low-latency algorithmic trading bot for scalping on Alpaca. Runs on Mac mini with iOS monitoring dashboard.

## Quick Start

### 1. Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Alpaca credentials
```

### 2. Train ML Model (First Time Only)
```bash
python engine/models/train.py
# Generates engine/models/scalp_v1.onnx
```

### 3. Run
```bash
# Paper trading (recommended)
MODE=paper python engine/main.py

# Or live
MODE=live python engine/main.py
```

Bot starts at `http://localhost:8765` for iOS app.

## Features

- **Hybrid Signal Engine**: Technical rules (40%) + ML model (60%)
- **Real-Time Data**: 1-second bars from Alpaca WebSocket
- **Execution Speed**: <1ms local, ~15-55ms end-to-end (realistic limit at retail)
- **Risk Management**: Daily loss cap (-2%), position limits, per-trade stops
- **iOS Dashboard**: Live P&L, positions, remote start/stop
- **Backtesting**: Walk-forward engine for strategy validation

## Architecture

```
Mac mini (Executor)              iPhone (Monitor)
├── Data Feed (WebSocket)        ├── Dashboard View
├── Signal Engine                ├── Positions View
│   ├── Rules (RSI, MACD, ...)   └── Control View
│   └── ML Model (ONNX)
├── Risk Manager                 
├── Order Router                 
└── API Server (FastAPI)─────────WebSocket─────→
```

## Configuration

Edit `.env`:
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` — from app.alpaca.markets
- `MODE` — paper or live
- `SYMBOLS` — SPY,QQQ,AAPL,TSLA,NVDA (comma-separated)
- Risk params: `DAILY_LOSS_CAP`, `MAX_CONCURRENT_POSITIONS`, `PER_TRADE_STOP_LOSS`

## Speed Optimizations

| Optimization | Latency Gain |
|---|---|
| uvloop | 2-4x async throughput |
| ONNX CoreML | ~5ms → 0.5ms inference |
| Numpy vectors | 10-100x vs loops |
| HTTP connection pooling | ~2ms saved per order |
| WebSocket data stream | Eliminates polling latency |

**Reality**: Alpaca retail API floor is 5-50ms. True nanoseconds require co-location (not available at retail).

## Risk Management (Non-Negotiable)

- Daily loss: -2% equity → hard stop
- Max positions: 5
- Per-trade stop: -0.3%
- Options delta cap: 0.5
- Consecutive loss cooldown: 3 losses → 15min break

## Files to Read

- **[CLAUDE.md](CLAUDE.md)** — Full technical docs, architecture, setup
- **[engine/main.py](engine/main.py)** — Bot orchestrator, entry point
- **[engine/config.py](engine/config.py)** — Settings management
- **[engine/signals/ensemble.py](engine/signals/ensemble.py)** — Signal generation

## Paper Trading First

Start with `MODE=paper` for 1-2 weeks to:
1. Validate fills and P&L logic
2. Monitor signal quality
3. Tune risk parameters
4. Measure latency profile

Only switch to `MODE=live` after paper validation.

## iOS App Setup

1. Open `ios/EdgeAI` in Xcode
2. Build and run on iPhone (same LAN as Mac mini)
3. Enter Mac mini IP in settings
4. Tap "Connect" for live updates

## Troubleshooting

**Bot won't connect to Alpaca:**
- Check API key/secret in `.env`
- Verify market hours (9:30-16:00 ET weekdays)

**No signals:**
- Wait for 20 bars (usually <1 min at 1s bars)
- Check `SYMBOLS` in `.env`

**Model not loading:**
- Run `python engine/models/train.py` first

See [CLAUDE.md](CLAUDE.md) for full troubleshooting.

## License

Internal use only. Do not share.
