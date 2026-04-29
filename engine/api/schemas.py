from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class PositionSnapshot(BaseModel):
    """Open position data"""
    symbol: str
    qty: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class BotStatus(BaseModel):
    """Bot operational status"""
    is_running: bool
    mode: str  # paper or live
    ready: bool
    equity: float
    cash: float
    daily_pnl: float
    positions: int
    trades_today: int


class LiveUpdate(BaseModel):
    """Real-time update message sent to iOS"""
    timestamp: str
    bot_status: BotStatus
    positions: List[PositionSnapshot]
    pnl: Dict


class FillLog(BaseModel):
    """Order fill record"""
    timestamp: str
    symbol: str
    side: str
    qty: float
    price: float
    status: str


class ControlCommand(BaseModel):
    """Command from iOS to bot"""
    action: str  # start, stop, pause
    symbols: Optional[List[str]] = None
    parameters: Optional[Dict] = None


class RiskParams(BaseModel):
    """Risk management parameters"""
    daily_loss_cap: float
    max_positions: int
    per_trade_stop: float
    max_position_pct: float


class BacktestResult(BaseModel):
    """Backtest results"""
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_hold_bars: float
    net_profit: float
