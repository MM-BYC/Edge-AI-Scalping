import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

from engine.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    total_equity: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_pnl: float = 0.0
    daily_loss_cap: float = settings.daily_loss_cap
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    position_count: int = 0
    consecutive_losses: int = 0


class RiskManager:
    """Hard risk controls and position limits"""

    def __init__(self):
        self.config = settings
        self.metrics = RiskMetrics()
        self.position_count = 0
        self.consecutive_loss_count = 0
        self.cooldown_until: Optional[datetime] = None
        self.daily_trades = 0
        self.max_daily_trades = 100

    def update_metrics(self, account_data: Dict):
        """Update risk metrics from account data"""
        try:
            self.metrics.total_equity = float(account_data.get("equity", 0))
            self.metrics.cash = float(account_data.get("cash", 0))
            self.metrics.positions_value = self.metrics.total_equity - self.metrics.cash
            self.metrics.realized_pnl = float(account_data.get("realized_pl", 0))
            self.metrics.unrealized_pnl = float(account_data.get("unrealized_pl", 0))
            self.metrics.daily_pnl = float(account_data.get("today_pl", 0))
            self.metrics.position_count = int(account_data.get("position_count", 0))

            logger.debug(
                f"Risk metrics: equity=${self.metrics.total_equity:.2f}, "
                f"daily_pnl=${self.metrics.daily_pnl:.2f}, positions={self.metrics.position_count}"
            )
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")

    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can initiate new trades"""

        # Check daily loss cap
        if self.metrics.daily_pnl <= (self.metrics.total_equity * self.config.daily_loss_cap):
            return False, f"Daily loss cap reached: ${self.metrics.daily_pnl:.2f}"

        # Check max positions
        if self.metrics.position_count >= self.config.max_concurrent_positions:
            return False, f"Max positions ({self.config.max_concurrent_positions}) reached"

        # Check cooldown after loss streak
        if self.cooldown_until is not None and datetime.now() < self.cooldown_until:
            return False, f"In cooldown period until {self.cooldown_until.isoformat()}"

        # Check daily trade limit
        if self.daily_trades >= self.max_daily_trades:
            return False, f"Daily trade limit ({self.max_daily_trades}) reached"

        return True, "OK"

    def can_enter_position(self, symbol: str, qty: float, entry_price: float) -> Tuple[bool, str]:
        """Check if we can enter a new position"""

        # Position size check
        position_value = qty * entry_price
        max_position_value = self.metrics.total_equity * 0.1  # Max 10% per position

        if position_value > max_position_value:
            return False, f"Position too large: ${position_value:.2f} > ${max_position_value:.2f}"

        # Available cash check
        if position_value > self.metrics.cash:
            return False, f"Insufficient cash: ${position_value:.2f} > ${self.metrics.cash:.2f}"

        return True, "OK"

    def validate_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Validate an order before submission"""

        if qty <= 0:
            return False, f"Invalid quantity: {qty}"

        if side not in ["buy", "sell"]:
            return False, f"Invalid side: {side}"

        if order_type not in ["market", "limit", "stop"]:
            return False, f"Invalid order type: {order_type}"

        if order_type == "limit" and limit_price is None:
            return False, "Limit price required for limit orders"

        if limit_price is not None and limit_price <= 0:
            return False, f"Invalid limit price: {limit_price}"

        return True, "OK"

    def on_trade_loss(self):
        """Handle a losing trade"""
        self.consecutive_loss_count += 1
        logger.warning(f"Consecutive losses: {self.consecutive_loss_count}")

        if self.consecutive_loss_count >= self.config.cooldown_trades:
            self.cooldown_until = datetime.now()
            import timedelta
            self.cooldown_until = self.cooldown_until.replace(
                second=self.cooldown_until.second + self.config.cooldown_minutes * 60
            )
            logger.warning(f"Entering cooldown period until {self.cooldown_until.isoformat()}")

    def on_trade_win(self):
        """Handle a winning trade"""
        self.consecutive_loss_count = 0

    def record_trade(self):
        """Record that a trade was executed"""
        self.daily_trades += 1

    def on_new_day(self):
        """Reset daily counters"""
        self.daily_trades = 0
        self.consecutive_loss_count = 0
        self.cooldown_until = None
        logger.info("Daily counters reset")

    def check_position_stop_loss(self, pnl_percent: float) -> bool:
        """Check if position should be stopped out"""
        if pnl_percent <= self.config.per_trade_stop_loss:
            logger.warning(f"Position stop loss triggered: {pnl_percent:.2%}")
            return True
        return False

    def get_status(self) -> Dict:
        """Get current risk status"""
        can_trade, msg = self.can_trade()
        return {
            "can_trade": can_trade,
            "trade_check_message": msg,
            "daily_pnl": self.metrics.daily_pnl,
            "equity": self.metrics.total_equity,
            "cash": self.metrics.cash,
            "positions": self.metrics.position_count,
            "consecutive_losses": self.consecutive_loss_count,
            "daily_trades": self.daily_trades,
            "in_cooldown": self.cooldown_until is not None and datetime.now() < self.cooldown_until
        }
