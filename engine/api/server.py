import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
import uvloop

from engine.config import settings
from engine.api.schemas import BotStatus, PositionSnapshot, LiveUpdate, ControlCommand
from engine.execution.pnl_tracker import PnLTracker
from engine.execution.risk import RiskManager
from engine.execution.options_tracker import OptionsTracker
from engine.execution.sell_put_router import SellPutRouter
from engine.execution.credit_spread_router import CreditSpreadRouter

logger = logging.getLogger(__name__)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected, {len(self.active_connections)} clients")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected, {len(self.active_connections)} clients")

    async def broadcast(self, message: Dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)


# ── Global state ──────────────────────────────────────────────────────
manager          = ConnectionManager()
pnl_tracker:     Optional[PnLTracker]       = None
risk_manager:    Optional[RiskManager]      = None
options_tracker: Optional[OptionsTracker]   = None
sell_put_router: Optional[SellPutRouter]    = None
credit_spread_router: Optional[CreditSpreadRouter] = None
data_feed: Optional[Any] = None
bot_is_running   = False
active_symbols:               Optional[List[str]] = None
active_sell_put_symbols:      Optional[List[str]] = None
active_credit_spread_symbols: Optional[List[str]] = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Edge AI Scalping API",
        description="iOS remote control and monitoring API",
        version="1.0",
    )

    @app.on_event("startup")
    async def startup():
        logger.info(f"API server starting on {settings.api_host}:{settings.api_port}")

    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    @app.get("/status")
    async def get_status():
        if risk_manager is None:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")
        return BotStatus(
            is_running=bot_is_running, mode=settings.mode, ready=True,
            equity=risk_manager.metrics.total_equity,
            cash=risk_manager.metrics.cash,
            daily_pnl=risk_manager.metrics.daily_pnl,
            positions=risk_manager.metrics.position_count,
            trades_today=risk_manager.daily_trades,
        )

    @app.get("/positions")
    async def get_positions():
        if pnl_tracker is None:
            raise HTTPException(status_code=503, detail="PnL tracker not initialized")
        return [PositionSnapshot(**t) for t in pnl_tracker.get_open_trades()]

    @app.get("/pnl")
    async def get_pnl():
        if pnl_tracker is None:
            raise HTTPException(status_code=503, detail="PnL tracker not initialized")
        return pnl_tracker.get_stats()

    @app.get("/risk")
    async def get_risk():
        if risk_manager is None:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")
        return risk_manager.get_status()

    @app.get("/symbols")
    async def get_symbols():
        return {
            "equity":        active_symbols or settings.symbols_list,
            "sell_put":      active_sell_put_symbols or [],
            "credit_spread": active_credit_spread_symbols or [],
        }

    @app.post("/control")
    async def control(command: ControlCommand) -> Dict:
        global bot_is_running, active_symbols
        global active_sell_put_symbols, active_credit_spread_symbols

        if command.action == "start":
            bot_is_running = True
            logger.info("Bot started by iOS")
            return {"status": "started"}

        elif command.action == "stop":
            bot_is_running = False
            logger.info("Bot stopped by iOS")
            return {"status": "stopped"}

        elif command.action == "pause":
            logger.info("Bot paused by iOS")
            return {"status": "paused"}

        elif command.action == "set_symbols":
            if not command.symbols:
                raise HTTPException(status_code=400, detail="symbols list is empty")
            active_symbols = [s.strip().upper() for s in command.symbols]
            logger.info(f"Equity symbols updated: {active_symbols}")
            return {"status": "symbols_updated", "symbols": active_symbols,
                    "note": "restart bot to subscribe new symbols"}

        elif command.action == "set_option_symbols":
            params = command.parameters or {}
            sp = params.get("sell_put", [])
            cs = params.get("credit_spread", [])
            active_sell_put_symbols      = [s.strip().upper() for s in sp]
            active_credit_spread_symbols = [s.strip().upper() for s in cs]
            if sell_put_router:
                sell_put_router.set_symbols(active_sell_put_symbols)
            if credit_spread_router:
                credit_spread_router.set_symbols(active_credit_spread_symbols)
            logger.info(f"Sell-put symbols: {active_sell_put_symbols}")
            logger.info(f"Credit-spread symbols: {active_credit_spread_symbols}")
            return {
                "status":          "option_symbols_updated",
                "sell_put":        active_sell_put_symbols,
                "credit_spread":   active_credit_spread_symbols,
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {command.action}")

    @app.get("/snapshot")
    async def get_snapshot():
        """Same payload as the WebSocket push — used by iOS pull-to-refresh."""
        if risk_manager is None or pnl_tracker is None:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        return _build_snapshot()

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                if risk_manager and pnl_tracker:
                    await websocket.send_json(_build_snapshot())
                await asyncio.sleep(0.5)

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
            manager.disconnect(websocket)

    @app.get("/backtest/latest")
    async def latest_backtest():
        return {
            "timestamp": datetime.now().isoformat(),
            "results": {
                "sharpe_ratio": 1.5, "max_drawdown": 0.08,
                "win_rate": 0.55, "total_trades": 125,
                "status": "example (run backtest to populate)",
            },
        }

    return app


def _build_snapshot() -> Dict:
    """Build the full live-update payload shared by WebSocket and /snapshot."""
    open_trades    = pnl_tracker.get_open_trades()
    winning_ticker = None
    if open_trades:
        best = max(open_trades, key=lambda t: t["unrealized_pnl"])
        if best["unrealized_pnl"] > 0:
            winning_ticker = best["symbol"]

    sp_positions = cs_positions = dte_positions = []
    sp_stats = cs_stats = dte_stats = None
    winning_sp = winning_cs = winning_dte = None

    if options_tracker:
        sp_positions  = options_tracker.get_sell_put_positions()
        cs_positions  = options_tracker.get_credit_spread_positions()
        dte_positions = options_tracker.get_zero_dte_positions()
        sp_stats      = options_tracker.get_sell_put_stats()
        cs_stats      = options_tracker.get_credit_spread_stats()
        dte_stats     = options_tracker.get_zero_dte_stats()
        winning_sp    = options_tracker.get_winning_sell_put()
        winning_cs    = options_tracker.get_winning_credit_spread()
        winning_dte   = options_tracker.get_winning_zero_dte()

    market_data = {}
    if data_feed:
        for symbol in settings.symbols_list:
            latest = data_feed.get_latest_bars(symbol, lookback=1)
            closes = latest.get("closes", [])
            timestamps = latest.get("timestamps", [])
            volumes = latest.get("volumes", [])
            if closes:
                timestamp = timestamps[-1] if timestamps else None
                if hasattr(timestamp, "isoformat"):
                    timestamp = timestamp.isoformat()

                market_data[symbol] = {
                    "symbol": symbol,
                    "price": closes[-1],
                    "timestamp": timestamp,
                    "volume": volumes[-1] if volumes else 0,
                    "bars": latest.get("count", 0),
                }

    return {
        "timestamp": datetime.now().isoformat(),
        "bot_status": {
            "is_running":   bot_is_running,
            "mode":         settings.mode,
            "equity":       risk_manager.metrics.total_equity,
            "cash":         risk_manager.metrics.cash,
            "daily_pnl":    risk_manager.metrics.daily_pnl,
            "positions":    risk_manager.metrics.position_count,
            "trades_today": risk_manager.daily_trades,
        },
        "market_data":             market_data,
        "positions":               open_trades,
        "pnl":                     pnl_tracker.get_stats(),
        "winning_ticker":           winning_ticker,
        "sell_put_positions":       sp_positions,
        "credit_spread_positions":  cs_positions,
        "zero_dte_positions":       dte_positions,
        "sell_put_stats":           sp_stats,
        "credit_spread_stats":      cs_stats,
        "zero_dte_stats":           dte_stats,
        "winning_sell_put":         winning_sp,
        "winning_credit_spread":    winning_cs,
        "winning_zero_dte":         winning_dte,
    }


def set_dependencies(
    pnl: PnLTracker,
    risk: RiskManager,
    opts: Optional[OptionsTracker] = None,
    feed: Optional[Any] = None,
    sp_router: Optional[SellPutRouter] = None,
    cs_router: Optional[CreditSpreadRouter] = None,
):
    global pnl_tracker, risk_manager, options_tracker, data_feed
    global sell_put_router, credit_spread_router
    pnl_tracker          = pnl
    risk_manager         = risk
    options_tracker      = opts
    data_feed            = feed
    sell_put_router      = sp_router
    credit_spread_router = cs_router


def set_bot_running(is_running: bool):
    global bot_is_running
    bot_is_running = is_running


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port,
                log_level=settings.api_log_level)
