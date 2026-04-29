import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvloop

from engine.config import settings
from engine.api.schemas import BotStatus, PositionSnapshot, LiveUpdate, ControlCommand
from engine.execution.pnl_tracker import PnLTracker
from engine.execution.risk import RiskManager

logger = logging.getLogger(__name__)

# Set high-performance async loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class ConnectionManager:
    """Manage WebSocket connections for iOS app"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected, {len(self.active_connections)} clients")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Client disconnected, {len(self.active_connections)} clients")

    async def broadcast(self, message: Dict):
        """Send message to all connected clients"""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(connection)


# Global state
manager = ConnectionManager()
pnl_tracker: Optional[PnLTracker] = None
risk_manager: Optional[RiskManager] = None
bot_is_running = False


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="Edge AI Scalping API",
        description="iOS remote control and monitoring API",
        version="1.0"
    )

    @app.on_event("startup")
    async def startup():
        logger.info(f"API server starting on {settings.api_host}:{settings.api_port}")

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("API server shutdown")

    @app.get("/health")
    async def health():
        """Health check endpoint"""
        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    @app.get("/status")
    async def get_status() -> BotStatus:
        """Get current bot status"""
        if risk_manager is None:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")

        return BotStatus(
            is_running=bot_is_running,
            mode=settings.mode,
            ready=True,
            equity=risk_manager.metrics.total_equity,
            cash=risk_manager.metrics.cash,
            daily_pnl=risk_manager.metrics.daily_pnl,
            positions=risk_manager.metrics.position_count,
            trades_today=risk_manager.daily_trades
        )

    @app.get("/positions")
    async def get_positions() -> List[PositionSnapshot]:
        """Get open positions"""
        if pnl_tracker is None:
            raise HTTPException(status_code=503, detail="PnL tracker not initialized")

        return [
            PositionSnapshot(**trade)
            for trade in pnl_tracker.get_open_trades()
        ]

    @app.get("/pnl")
    async def get_pnl() -> Dict:
        """Get P&L stats"""
        if pnl_tracker is None:
            raise HTTPException(status_code=503, detail="PnL tracker not initialized")

        return pnl_tracker.get_stats()

    @app.get("/risk")
    async def get_risk() -> Dict:
        """Get risk management status"""
        if risk_manager is None:
            raise HTTPException(status_code=503, detail="Risk manager not initialized")

        return risk_manager.get_status()

    @app.post("/control")
    async def control(command: ControlCommand) -> Dict:
        """Execute control command from iOS"""
        global bot_is_running

        if command.action == "start":
            bot_is_running = True
            logger.info(f"Bot started by iOS")
            return {"status": "started"}

        elif command.action == "stop":
            bot_is_running = False
            logger.info(f"Bot stopped by iOS")
            return {"status": "stopped"}

        elif command.action == "pause":
            logger.info(f"Bot paused by iOS")
            return {"status": "paused"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {command.action}")

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        """WebSocket endpoint for live updates"""
        await manager.connect(websocket)
        logger.info("WebSocket client connected, starting live updates")

        try:
            while True:
                if risk_manager and pnl_tracker:
                    try:
                        update = {
                            "timestamp": datetime.now().isoformat(),
                            "bot_status": {
                                "is_running": bot_is_running,
                                "mode": settings.mode,
                                "equity": risk_manager.metrics.total_equity,
                                "cash": risk_manager.metrics.cash,
                                "daily_pnl": risk_manager.metrics.daily_pnl,
                                "positions": risk_manager.metrics.position_count,
                                "trades_today": risk_manager.daily_trades
                            },
                            "positions": pnl_tracker.get_open_trades(),
                            "pnl": pnl_tracker.get_stats()
                        }
                        await websocket.send_json(update)
                    except Exception as e:
                        logger.error(f"Error sending WebSocket update: {e}", exc_info=True)
                        break
                await asyncio.sleep(0.5)

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            manager.disconnect(websocket)

    @app.get("/backtest/latest")
    async def latest_backtest() -> Dict:
        """Get latest backtest results"""
        return {
            "timestamp": datetime.now().isoformat(),
            "results": {
                "sharpe_ratio": 1.5,
                "max_drawdown": 0.08,
                "win_rate": 0.55,
                "total_trades": 125,
                "status": "example (run backtest to populate)"
            }
        }

    return app


def set_dependencies(pnl: PnLTracker, risk: RiskManager):
    """Inject dependencies (called by main.py)"""
    global pnl_tracker, risk_manager
    pnl_tracker = pnl
    risk_manager = risk


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.api_log_level
    )
