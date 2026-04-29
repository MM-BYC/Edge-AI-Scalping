import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np

from engine.agents.base_agent import BaseAgent
from engine.config import settings

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    _ALPACA_DATA_OK = True
except ImportError:
    _ALPACA_DATA_OK = False
    logger.warning("alpaca-py data client not available — synthetic data will be used")


class DataAgent(BaseAgent):
    """
    Downloads 1-minute OHLCV bars from Alpaca for every configured symbol.
    All symbols are fetched concurrently via asyncio.gather.
    Falls back to synthetic data when the library is unavailable (dev/test).
    """

    name = "data_agent"

    def __init__(self, bus: asyncio.Queue):
        super().__init__(bus)
        if _ALPACA_DATA_OK:
            self._client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )

    async def run(self, symbols: List[str], lookback_days: int = 90) -> Dict:
        self.logger.info(f"Fetching {lookback_days}d of 1-min bars for {symbols}")

        if not _ALPACA_DATA_OK:
            data = self._synthetic(symbols, lookback_days)
            await self.publish("data_ready", data)
            return data

        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self._fetch, sym, lookback_days)
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dataset: Dict = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to fetch {sym}: {result}")
            elif result is not None:
                dataset[sym] = result
                self.logger.info(f"{sym}: {len(result['closes'])} bars fetched")

        await self.publish("data_ready", dataset)
        return dataset

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _fetch(self, symbol: str, lookback_days: int) -> Optional[Dict]:
        import pandas as pd  # guarded import — only runs when _ALPACA_DATA_OK

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed="iex",
        )
        resp = self._client.get_stock_bars(req)
        df = resp.df
        if df.empty:
            return None

        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        df = df.sort_index()

        # Keep only regular market hours (9:30–16:00 ET)
        et = df.index.tz_convert("America/New_York")
        mask = (et.time >= pd.Timestamp("09:30").time()) & (et.time <= pd.Timestamp("16:00").time())
        df = df[mask]
        if df.empty:
            return None

        return {
            "opens":      df["open"].values.astype(np.float32),
            "highs":      df["high"].values.astype(np.float32),
            "lows":       df["low"].values.astype(np.float32),
            "closes":     df["close"].values.astype(np.float32),
            "volumes":    df["volume"].values.astype(np.float32),
            "timestamps": df.index.astype(str).tolist(),
        }

    @staticmethod
    def _synthetic(symbols: List[str], lookback_days: int) -> Dict:
        """Geometric Brownian Motion stand-in for offline development."""
        n = lookback_days * 390  # ~390 1-min bars per trading day
        dataset: Dict = {}
        rng = np.random.default_rng(42)
        for sym in symbols:
            log_ret = rng.normal(0, 0.001, n)
            price = 100.0 * np.exp(np.cumsum(log_ret)).astype(np.float32)
            noise = rng.normal(0, 0.0005, n).astype(np.float32)
            opens = price * (1 + noise)
            highs = np.maximum(opens, price) * (1 + np.abs(rng.normal(0, 0.001, n))).astype(np.float32)
            lows  = np.minimum(opens, price) * (1 - np.abs(rng.normal(0, 0.001, n))).astype(np.float32)
            vols  = rng.integers(1000, 50_000, n).astype(np.float32)
            dataset[sym] = {
                "opens": opens, "highs": highs, "lows": lows,
                "closes": price, "volumes": vols, "timestamps": [],
            }
        return dataset
