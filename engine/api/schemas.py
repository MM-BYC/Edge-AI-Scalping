from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime


class PositionSnapshot(BaseModel):
    """Open equity position data"""
    symbol: str
    qty: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class OptionPositionSnapshot(BaseModel):
    """Open option position (sell put or credit spread)"""
    symbol: str
    strategy: str               # "sell_put" or "credit_spread"
    strike: float
    upper_strike: Optional[float] = None
    expiry: str
    premium_collected: float
    current_value: float
    qty: int
    unrealized_pnl: float
    unrealized_pnl_pct: float
    days_to_expiry: int
    delta: float
    theta: float


class OptionStats(BaseModel):
    """Aggregate stats for one option strategy bucket"""
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    open_positions: int
    win_rate: float


class BotStatus(BaseModel):
    """Bot operational status"""
    is_running: bool
    mode: str
    ready: bool
    equity: float
    cash: float
    daily_pnl: float
    positions: int
    trades_today: int


class LiveUpdate(BaseModel):
    """Real-time update message sent to iOS every 500 ms"""
    timestamp: str
    bot_status: BotStatus
    positions: List[PositionSnapshot]
    pnl: Dict
    winning_ticker: Optional[str] = None
    sell_put_positions: List[OptionPositionSnapshot] = []
    credit_spread_positions: List[OptionPositionSnapshot] = []
    zero_dte_positions: List[OptionPositionSnapshot] = []
    winning_sell_put: Optional[str] = None
    winning_credit_spread: Optional[str] = None
    winning_zero_dte: Optional[str] = None
    sell_put_stats: Optional[Dict] = None
    credit_spread_stats: Optional[Dict] = None
    zero_dte_stats: Optional[Dict] = None


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
    action: str
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
