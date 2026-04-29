import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional

from engine.broker.alpaca_client import AlpacaClient, Bar
from engine.data.buffer import BarBuffer
from engine.config import settings

logger = logging.getLogger(__name__)


class DataFeed:
    """Real-time market data feed manager"""

    def __init__(self, alpaca_client: AlpacaClient):
        self.alpaca = alpaca_client
        self.buffers: Dict[str, BarBuffer] = {}
        self.callbacks: List[Callable] = []
        self.is_running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._last_bar_timestamp: Dict[str, datetime] = {}

        for symbol in settings.symbols_list:
            self.buffers[symbol] = BarBuffer(symbol, max_bars=500)
            self.alpaca.subscribe_bars(symbol, self._on_bar)

    def add_callback(self, callback: Callable):
        """Register callback to be called when a new bar arrives"""
        self.callbacks.append(callback)

    def get_buffer(self, symbol: str) -> Optional[BarBuffer]:
        """Get the buffer for a symbol"""
        return self.buffers.get(symbol)

    def is_ready(self, min_bars: int = 20) -> bool:
        """Check if all buffers have minimum bars"""
        return all(buf.is_ready(min_bars) for buf in self.buffers.values())

    def all_ready_symbols(self) -> List[str]:
        """Get list of symbols with enough bars"""
        return [symbol for symbol, buf in self.buffers.items() if buf.is_ready(20)]

    async def start(self):
        """Start the feed (connects to data source)"""
        self.is_running = True
        await self.alpaca.connect()
        self._poll_task = asyncio.create_task(self._poll_latest_bars())
        logger.info(f"Data feed started for symbols: {list(self.buffers.keys())}")

    async def stop(self):
        """Stop the feed"""
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        await self.alpaca.disconnect()
        logger.info("Data feed stopped")

    async def _poll_latest_bars(self):
        """Poll Alpaca latest bars and fan them into the same callbacks as a stream."""
        symbols = list(self.buffers.keys())
        interval = max(float(settings.market_data_poll_seconds), 1.0)

        while self.is_running:
            try:
                bars = await self.alpaca.get_latest_bars(symbols)
                for symbol, bar in bars.items():
                    last_ts = self._last_bar_timestamp.get(symbol)
                    if last_ts is not None and bar.timestamp <= last_ts:
                        continue
                    self._last_bar_timestamp[symbol] = bar.timestamp
                    self._on_bar(bar)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Market data poll error: {e}")

            await asyncio.sleep(interval)

    def _on_bar(self, bar: Bar):
        """Handle incoming bar (called by broker)"""
        if bar.symbol not in self.buffers:
            return

        # Add to buffer
        buffer = self.buffers[bar.symbol]
        buffer.append(
            timestamp=bar.timestamp,
            open_=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume
        )

        # Trigger callbacks
        for callback in self.callbacks:
            try:
                callback(bar)
            except Exception as e:
                logger.error(f"Error in feed callback: {e}")

    def get_latest_bars(self, symbol: str, lookback: int = 20) -> Dict:
        """Get latest bars for a symbol"""
        buffer = self.buffers.get(symbol)
        if not buffer:
            return {}

        timestamps, opens, highs, lows, closes, volumes = buffer.get_numpy_arrays(lookback)

        return {
            "symbol": symbol,
            "timestamps": timestamps.tolist() if len(timestamps) > 0 else [],
            "opens": opens.tolist() if len(opens) > 0 else [],
            "highs": highs.tolist() if len(highs) > 0 else [],
            "lows": lows.tolist() if len(lows) > 0 else [],
            "closes": closes.tolist() if len(closes) > 0 else [],
            "volumes": volumes.tolist() if len(volumes) > 0 else [],
            "count": len(closes)
        }

    def __repr__(self) -> str:
        return f"DataFeed({len(self.buffers)} symbols)"
