import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass

from engine.broker.alpaca_client import AlpacaClient
from engine.execution.risk import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLog:
    """Log entry for order execution"""
    timestamp: datetime
    symbol: str
    signal: int
    order_type: str
    qty: float
    side: str
    entry_price: float
    status: str  # submitted, filled, rejected, cancelled


class OrderRouter:
    """Route signals to orders with risk management"""

    def __init__(self, alpaca_client: AlpacaClient, risk_manager: RiskManager):
        self.alpaca = alpaca_client
        self.risk = risk_manager
        self.execution_log: List[ExecutionLog] = []
        self.open_orders: Dict[str, Dict] = {}
        self.pending_symbols = set()

    async def route_signal(self, symbol: str, signal: int, current_price: float, confidence: float = 0.5):
        """
        Route a trading signal to order submission
        signal: -1 (sell), 0 (hold), 1 (buy)
        """

        # Check if we can trade
        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"Cannot trade {symbol}: {reason}")
            return None

        # Skip hold signal
        if signal == 0:
            return None

        # Avoid duplicate orders
        if symbol in self.pending_symbols:
            logger.debug(f"Skipping {symbol}: already have pending order")
            return None

        # Determine position size (2% of equity per trade)
        position_size_pct = 0.02
        position_value = self.risk.metrics.total_equity * position_size_pct
        qty = max(1, int(position_value / current_price))

        # Buy signal
        if signal == 1:
            can_enter, msg = self.risk.can_enter_position(symbol, qty, current_price)
            if not can_enter:
                logger.warning(f"Cannot enter {symbol}: {msg}")
                return None

            order = await self._submit_entry_order(symbol, qty, current_price, "buy")
            if order:
                self.pending_symbols.add(symbol)

        # Sell signal (close position)
        elif signal == -1:
            # For now, just log (close positions separately via stop losses)
            logger.info(f"Sell signal for {symbol} (position closing logic handled elsewhere)")

        return order

    async def _submit_entry_order(self, symbol: str, qty: float, price: float, side: str) -> Optional[Dict]:
        """Submit a scalping entry order (market or limit)"""
        try:
            # Use market order for faster entry
            order_data = await self.alpaca.submit_market_order(symbol, qty, side)

            if order_data and "id" in order_data:
                log_entry = ExecutionLog(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    signal=1 if side == "buy" else -1,
                    order_type="market",
                    qty=qty,
                    side=side,
                    entry_price=price,
                    status="submitted"
                )
                self.execution_log.append(log_entry)
                self.risk.record_trade()

                logger.info(f"Entry order submitted: {symbol} {qty} {side} @ market (~${price:.2f})")
                return order_data
            else:
                logger.error(f"Order submission failed: {order_data}")
                return None

        except Exception as e:
            logger.error(f"Error submitting entry order for {symbol}: {e}")
            return None

    async def close_position(self, symbol: str, price: float, reason: str = "manual") -> Optional[Dict]:
        """Close an open position"""
        try:
            # Get current position
            positions = await self.alpaca.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position:
                logger.debug(f"No open position for {symbol}")
                return None

            qty = float(position["qty"])
            side = "sell" if qty > 0 else "buy"

            # Submit market close order
            order_data = await self.alpaca.submit_market_order(symbol, abs(qty), side)

            if order_data and "id" in order_data:
                logger.info(f"Position closed: {symbol} {qty} @ market (~${price:.2f}) ({reason})")
                self.pending_symbols.discard(symbol)
                return order_data
            else:
                logger.error(f"Position close failed: {order_data}")
                return None

        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            return None

    async def close_all_positions(self, reason: str = "market close"):
        """Close all open positions"""
        try:
            positions = await self.alpaca.get_positions()
            for position in positions:
                await self.close_position(position["symbol"], float(position["last_price"]), reason)
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")

    def get_execution_log(self, symbol: Optional[str] = None, limit: int = 100) -> List[ExecutionLog]:
        """Get execution log"""
        if symbol:
            return [e for e in self.execution_log if e.symbol == symbol][-limit:]
        return self.execution_log[-limit:]

    def get_performance_summary(self) -> Dict:
        """Get simple performance summary"""
        if not self.execution_log:
            return {"trades": 0}

        total_trades = len(self.execution_log)
        submitted_trades = sum(1 for e in self.execution_log if e.status == "submitted")

        return {
            "total_executions": total_trades,
            "submitted_orders": submitted_trades,
            "log_entries": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "symbol": e.symbol,
                    "side": e.side,
                    "qty": e.qty,
                    "price": e.entry_price,
                    "status": e.status
                }
                for e in self.execution_log[-20:]  # Last 20 orders
            ]
        }
