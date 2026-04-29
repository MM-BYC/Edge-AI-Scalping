import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FillEvent:
    """Record of an order fill"""
    timestamp: datetime
    symbol: str
    side: str  # buy or sell
    qty: float
    price: float
    commission: float = 0.0
    order_id: str = ""


@dataclass
class TradeSnapshot:
    """Open trade snapshot"""
    symbol: str
    entry_time: datetime
    entry_price: float
    entry_qty: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    bars_held: int = 0


class PnLTracker:
    """Track realized and unrealized P&L"""

    def __init__(self):
        self.fills: List[FillEvent] = []
        self.trades: Dict[str, TradeSnapshot] = {}
        self.daily_stats = {
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "commissions": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_trades": 0
        }

    def record_fill(self, symbol: str, side: str, qty: float, price: float, order_id: str = ""):
        """Record an order fill"""
        fill = FillEvent(
            timestamp=datetime.now(),
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            order_id=order_id
        )
        self.fills.append(fill)

        if side == "buy":
            # Open or add to position
            if symbol in self.trades:
                trade = self.trades[symbol]
                # Average up
                total_qty = trade.entry_qty + qty
                trade.entry_price = (trade.entry_price * trade.entry_qty + price * qty) / total_qty
                trade.entry_qty = total_qty
            else:
                self.trades[symbol] = TradeSnapshot(
                    symbol=symbol,
                    entry_time=datetime.now(),
                    entry_price=price,
                    entry_qty=qty
                )
        elif side == "sell":
            # Close or reduce position
            if symbol in self.trades:
                trade = self.trades[symbol]
                if qty >= trade.entry_qty:
                    # Close entire position
                    pnl = (price - trade.entry_price) * trade.entry_qty
                    self.daily_stats["realized_pnl"] += pnl

                    if pnl > 0:
                        self.daily_stats["winning_trades"] += 1
                    else:
                        self.daily_stats["losing_trades"] += 1

                    self.daily_stats["total_trades"] += 1
                    del self.trades[symbol]
                    logger.info(f"Trade closed: {symbol}, P&L = ${pnl:.2f}")
                else:
                    # Partial close
                    pnl = (price - trade.entry_price) * qty
                    self.daily_stats["realized_pnl"] += pnl
                    trade.entry_qty -= qty
                    logger.info(f"Partial close: {symbol}, P&L = ${pnl:.2f}")

    def update_market_prices(self, symbol: str, current_price: float):
        """Update current price for open positions"""
        if symbol in self.trades:
            trade = self.trades[symbol]
            trade.current_price = current_price
            trade.unrealized_pnl = (current_price - trade.entry_price) * trade.entry_qty
            trade.unrealized_pnl_pct = (current_price - trade.entry_price) / trade.entry_price if trade.entry_price > 0 else 0
            trade.bars_held += 1

    def update_all_prices(self, prices: Dict[str, float]):
        """Update prices for all symbols"""
        for symbol, price in prices.items():
            self.update_market_prices(symbol, price)

    def get_unrealized_pnl(self) -> float:
        """Sum of unrealized P&L across all open trades"""
        return sum(trade.unrealized_pnl for trade in self.trades.values())

    def get_total_pnl(self) -> float:
        """Total P&L (realized + unrealized)"""
        return self.daily_stats["realized_pnl"] + self.get_unrealized_pnl()

    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        return [
            {
                "symbol": trade.symbol,
                "entry_time": trade.entry_time.isoformat(),
                "entry_price": trade.entry_price,
                "qty": trade.entry_qty,
                "current_price": trade.current_price,
                "unrealized_pnl": trade.unrealized_pnl,
                "unrealized_pnl_pct": trade.unrealized_pnl_pct,
                "bars_held": trade.bars_held
            }
            for trade in self.trades.values()
        ]

    def get_stats(self) -> Dict:
        """Get performance statistics"""
        total_trades = self.daily_stats["total_trades"]
        win_rate = (
            self.daily_stats["winning_trades"] / total_trades * 100
            if total_trades > 0 else 0
        )

        return {
            "realized_pnl": self.daily_stats["realized_pnl"],
            "unrealized_pnl": self.get_unrealized_pnl(),
            "total_pnl": self.get_total_pnl(),
            "winning_trades": self.daily_stats["winning_trades"],
            "losing_trades": self.daily_stats["losing_trades"],
            "total_trades": total_trades,
            "win_rate_pct": win_rate,
            "open_positions": len(self.trades),
            "open_trades": self.get_open_trades()
        }

    def reset_daily(self):
        """Reset daily stats (call at market close)"""
        self.daily_stats = {
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "commissions": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_trades": 0
        }
        self.trades.clear()
        logger.info("Daily stats reset")
