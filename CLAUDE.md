# Edge AI Scalping Bot — Technical Documentation

## Project Overview
Local-first algorithmic trading bot optimized for scalping (seconds to minutes) on US Stocks and Options via Alpaca broker. Runs on Mac mini as primary executor, with SwiftUI iOS app for monitoring and remote control.

## Architecture

### Core Components

**1. Data Pipeline** (`engine/data/`)
- `feed.py`: Real-time bar stream from Alpaca WebSocket
- `buffer.py`: Circular OHLCV buffers (500 bars per symbol) with thread-safe numpy views

**2. Signal Generation** (`engine/signals/`)
- `rules.py`: Technical indicators (RSI, MACD, VWAP, ATR, EMA) using pandas-ta vectorized
- `ml_inference.py`: ONNX model inference with CoreML acceleration (Apple Neural Engine)
- `ensemble.py`: Weighted vote (40% rules, 60% ML) → {-1, 0, 1} signal

**3. Execution** (`engine/execution/`)
- `risk.py`: Hard guards (daily loss cap -2%, max 5 positions, -0.3% stop loss per trade, 3-loss cooldown)
- `router.py`: Signal → order routing with position sizing (2% per trade)
- `pnl_tracker.py`: Realized/unrealized P&L tracking

**4. Broker Integration** (`engine/broker/`)
- `alpaca_client.py`: async httpx wrapper for Alpaca REST + callback system for fills

**5. API Server** (`engine/api/`)
- `server.py`: FastAPI with WebSocket live updates to iOS (500ms push rate)
- `schemas.py`: Pydantic models for iOS communication

**6. Orchestration**
- `main.py`: Event loop coordinator (uvloop), signal router, fill tracker
- `config.py`: Pydantic settings loader from .env

### ML Model Pipeline (`engine/models/`)
- `train.py`: LightGBM classifier trained on 1-minute OHLCV features (20-dim input, 3-class output: sell/hold/buy)
- Exports to ONNX via onnxmltools
- Uses CoreML execution provider on M-series Macs for ~0.5ms inference

### Backtesting (`engine/backtest/`)
- `engine.py`: Walk-forward simulator replaying signal ensemble on historical bars
- Metrics: Sharpe, max drawdown, win rate, profit factor, average hold time

## Tech Stack

| Layer | Tech | Why |
|---|---|---|
| Runtime | Python 3.11 + uvloop | 2-4x faster asyncio |
| Async | httpx + FastAPI | Non-blocking I/O throughout |
| ML | ONNX + CoreML EP | 0.5ms inference, no PyTorch |
| Broker | alpaca-py (v2) | Official SDK, WebSocket streaming |
| Indicators | pandas-ta + numpy | Vectorized, 10-100x faster than loops |
| Backtest | Custom walk-forward | Replay signal logic on historical data |
| iOS | SwiftUI + URLSession WebSocket | Native iOS networking |

## Execution Speed Targets
- **Local signal → order**: <1ms (numpy + ONNX)
- **Order dispatch**: ~2ms (httpx persistent session)
- **Alpaca fill**: 10–50ms (network latency, unavoidable at retail)
- **End-to-end**: ~15–55ms (realistic, not nanoseconds)

Retail Alpaca API round-trip floor is ~5–50ms due to network — cannot be optimized away. True nanoseconds require exchange co-location.

## File Structure

```
engine/
├── main.py                    # Entry point, orchestrator
├── config.py                  # Settings from .env
├── broker/
│   ├── alpaca_client.py       # Alpaca API wrapper
│   └── __init__.py
├── data/
│   ├── feed.py               # Data ingest
│   ├── buffer.py             # Circular OHLCV buffers
│   └── __init__.py
├── signals/
│   ├── rules.py              # Technical indicators
│   ├── ml_inference.py       # ONNX model inference
│   ├── ensemble.py           # Signal combiner
│   └── __init__.py
├── execution/
│   ├── risk.py               # Risk guards
│   ├── router.py             # Signal → orders
│   ├── pnl_tracker.py        # P&L tracking
│   └── __init__.py
├── backtest/
│   ├── engine.py             # Walk-forward backtester
│   └── __init__.py
├── api/
│   ├── server.py             # FastAPI app
│   ├── schemas.py            # Pydantic models
│   └── __init__.py
└── models/
    ├── train.py              # Model training
    ├── scalp_v1.onnx         # Trained model (generated)
    └── __init__.py

ios/
└── EdgeAI/
    ├── App.swift
    ├── Views/
    │   ├── DashboardView.swift
    │   ├── PositionsView.swift
    │   └── ControlView.swift
    └── Services/
        ├── BotService.swift
        └── NotificationService.swift

tests/
├── test_signals.py
├── test_risk.py
└── test_backtest.py

.env.example                  # Configuration template
requirements.txt              # Python dependencies
```

## Setup & Run

### 1. Install `uv` (Fast Python Manager)

```bash
# macOS
brew install uv

# Or via pip
pip install uv
```

### 2. Install Dependencies

```bash
uv sync  # Creates venv and installs dependencies
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with Alpaca credentials (get from app.alpaca.markets)
```

### 4. Train Model (Optional)

```bash
uv run -- python engine/models/train.py
# Generates engine/models/scalp_v1.onnx
```

### 5. Run Bot

```bash
# Paper trading (recommended first)
uv run -- python engine/main.py
```

Set `MODE=paper` in `.env`. API available at `http://localhost:8765` for iOS app.

### 6. Run Tests

```bash
uv run -- pytest tests/ -v
```

### 7. Backtest

```bash
uv run -- python -c "from engine.backtest.engine import BacktestEngine; ..."
```

## Configuration

Key settings in `.env`:
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`: Alpaca credentials
- `MODE`: paper or live
- `SYMBOLS`: Comma-separated tickers (SPY,QQQ,AAPL,TSLA,NVDA)
- `DAILY_LOSS_CAP`: -0.02 (hard stop at -2% equity per day)
- `MAX_CONCURRENT_POSITIONS`: 5
- `PER_TRADE_STOP_LOSS`: -0.003 (-0.3% stop per position)
- `ML_MODEL_PATH`: engine/models/scalp_v1.onnx

## iOS App

### Architecture
- SwiftUI views: Dashboard (P&L chart), Positions (greeks), Control (start/stop/config)
- BotService: WebSocket client, auto-reconnect on LAN
- NotificationService: Local push notifications (no APNs server needed)

### Setup
1. Open `ios/EdgeAI` in Xcode
2. Build and run on iPhone/iPad on same LAN as Mac mini
3. Enter Mac mini IP/hostname in settings
4. Tap "Connect" → live P&L updates

## Risk Management

**Hard Stops (Cannot Trade Without):**
- Daily loss cap: -2% equity → no more trades rest of day
- Max 5 concurrent positions
- Per-trade stop: -0.3%
- Options max delta: 0.5
- Consecutive loss cooldown: 3 losses → 15min break

**Position Sizing:**
- 2% of equity per entry trade
- Max 10% per position
- Scalp holds: typically 1–5 bars (seconds to minutes)

## Performance Monitoring

**Logs** (to stdout + optional file):
- Signal generation (symbol, direction, confidence)
- Order submissions/fills
- P&L updates every 5 sec
- Risk check failures

**Real-Time Dashboard** (iOS app):
- Live equity curve (Charts framework)
- Open positions with P&L %
- Recent fills (symbol, side, qty, price)
- Bot status (running/paused/stopped)

**Metrics** (`/pnl` endpoint):
- Realized/unrealized P&L
- Win rate
- Avg hold time
- Profit factor

## Known Limitations

1. **Latency**: Alpaca retail API floor ~5–50ms per order. Cannot achieve sub-millisecond fills.
2. **iOS Background**: Cannot run bot on iPhone (iOS kills background processes). iPhone is monitor + control only.
3. **Backtesting**: Simple walk-forward simulation, does not account for slippage/partial fills at scale.
4. **ML**: Requires training data; dummy ONNX model provided if LightGBM not installed.
5. **Forex**: Not supported via Alpaca; focus on US Stocks + Options only.

## Future Enhancements

- [ ] WebSocket streaming order book (instead of REST polling)
- [ ] Partial fill tracking
- [ ] Dynamic position sizing (kelly criterion)
- [ ] Multi-asset optimization (correlation-aware)
- [ ] Real-time backtesting on new data
- [ ] Push notifications to iOS (APNs)
- [ ] Slack/email alerts
- [ ] Graphical strategy builder

## Troubleshooting

**Bot won't start:**
- Check `.env` has valid Alpaca API key/secret
- Verify market hours (9:30–16:00 ET weekdays)
- Check mode (paper vs live) matches account

**No signals generating:**
- Wait for 20 bars (usually <1 minute at 1s bars)
- Check symbol has active market data
- Verify `SYMBOLS` in .env

**API not responding:**
- Ensure port 8765 is not in use
- Check firewall allows connections
- Verify iOS on same LAN as Mac mini

**ML model not found:**
- Run `python engine/models/train.py` first
- Or set `ML_MODEL_PATH` to existing .onnx file

## References

- Alpaca API: https://docs.alpaca.markets
- onnxruntime: https://onnxruntime.ai
- LightGBM: https://lightgbm.readthedocs.io
- FastAPI: https://fastapi.tiangolo.com
