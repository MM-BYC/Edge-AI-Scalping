import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, Optional, List
import httpx
from dataclasses import dataclass

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from engine.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Bar:
    """1-second OHLCV bar"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class AlpacaClient:
    def __init__(self):
        self.config = settings
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url
        )
        self.http_client = httpx.AsyncClient(
            base_url=settings.alpaca_base_url,
            headers={
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            },
            timeout=30.0
        )
        self.bar_callbacks: Dict[str, List[Callable]] = {}
        self.fill_callbacks: Dict[str, List[Callable]] = {}
        self.is_connected = False

    async def connect(self):
        """Establish WebSocket connection for streaming data"""
        self.is_connected = True
        logger.info("Alpaca client initialized")

    async def disconnect(self):
        """Close connections"""
        await self.http_client.aclose()
        self.is_connected = False
        logger.info("Alpaca client disconnected")

    def subscribe_bars(self, symbol: str, callback: Callable):
        """Register callback for bar updates"""
        if symbol not in self.bar_callbacks:
            self.bar_callbacks[symbol] = []
        self.bar_callbacks[symbol].append(callback)

    def subscribe_fills(self, symbol: str, callback: Callable):
        """Register callback for order fills"""
        if symbol not in self.fill_callbacks:
            self.fill_callbacks[symbol] = []
        self.fill_callbacks[symbol].append(callback)

    async def get_account(self):
        """Fetch account info"""
        response = await self.http_client.get("/v2/account")
        return response.json()

    async def get_positions(self):
        """Fetch open positions"""
        response = await self.http_client.get("/v2/positions")
        return response.json()

    async def get_orders(self, status: str = "open"):
        """Fetch orders by status"""
        response = await self.http_client.get(f"/v2/orders", params={"status": status})
        return response.json()

    async def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Submit market order"""
        order_data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": time_in_force
        }
        response = await self.http_client.post("/v2/orders", json=order_data)
        result = response.json()
        logger.info(f"Market order submitted: {symbol} {qty} {side} -> {result.get('id', 'ERROR')}")
        return result

    async def submit_limit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Submit limit order"""
        order_data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "limit",
            "limit_price": limit_price,
            "time_in_force": time_in_force
        }
        response = await self.http_client.post("/v2/orders", json=order_data)
        result = response.json()
        logger.info(f"Limit order submitted: {symbol} {qty} {side} @ {limit_price}")
        return result

    async def submit_stop_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        stop_price: float,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Submit stop-loss order"""
        order_data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "stop",
            "stop_price": stop_price,
            "time_in_force": time_in_force
        }
        response = await self.http_client.post("/v2/orders", json=order_data)
        result = response.json()
        logger.info(f"Stop order submitted: {symbol} {qty} {side} @ stop {stop_price}")
        return result

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        response = await self.http_client.delete(f"/v2/orders/{order_id}")
        logger.info(f"Order cancelled: {order_id}")
        return response.status_code == 204

    async def cancel_all_orders(self):
        """Cancel all open orders"""
        response = await self.http_client.delete("/v2/orders")
        logger.info(f"All orders cancelled")
        return response.json()

    def _trigger_bar_callbacks(self, symbol: str, bar: Bar):
        """Trigger all callbacks for a symbol's bar"""
        if symbol in self.bar_callbacks:
            for callback in self.bar_callbacks[symbol]:
                try:
                    callback(bar)
                except Exception as e:
                    logger.error(f"Error in bar callback for {symbol}: {e}")

    def _trigger_fill_callbacks(self, symbol: str, fill_data: Dict):
        """Trigger all callbacks for a symbol's fill"""
        if symbol in self.fill_callbacks:
            for callback in self.fill_callbacks[symbol]:
                try:
                    callback(fill_data)
                except Exception as e:
                    logger.error(f"Error in fill callback for {symbol}: {e}")
