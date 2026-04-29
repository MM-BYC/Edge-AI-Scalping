import numpy as np
from collections import deque
from datetime import datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BarBuffer:
    """Circular buffer for OHLCV bars with numpy views"""

    def __init__(self, symbol: str, max_bars: int = 500):
        self.symbol = symbol
        self.max_bars = max_bars

        # Circular buffer for each field
        self.timestamps = deque(maxlen=max_bars)
        self.opens = deque(maxlen=max_bars)
        self.highs = deque(maxlen=max_bars)
        self.lows = deque(maxlen=max_bars)
        self.closes = deque(maxlen=max_bars)
        self.volumes = deque(maxlen=max_bars)

        self._lock = False

    def append(self, timestamp: datetime, open_: float, high: float, low: float, close: float, volume: int):
        """Add a new bar (thread-safe)"""
        while self._lock:
            pass
        self._lock = True
        try:
            self.timestamps.append(timestamp)
            self.opens.append(open_)
            self.highs.append(high)
            self.lows.append(low)
            self.closes.append(close)
            self.volumes.append(volume)
        finally:
            self._lock = False

    def get_numpy_arrays(self, lookback: int = 100) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Get OHLCV as numpy arrays for the last N bars"""
        while self._lock:
            pass
        self._lock = True
        try:
            n = min(lookback, len(self.closes))
            closes_list = list(self.closes)[-n:] if n > 0 else []
            opens_list = list(self.opens)[-n:] if n > 0 else []
            highs_list = list(self.highs)[-n:] if n > 0 else []
            lows_list = list(self.lows)[-n:] if n > 0 else []
            volumes_list = list(self.volumes)[-n:] if n > 0 else []
            timestamps_list = list(self.timestamps)[-n:] if n > 0 else []

            return (
                np.array(timestamps_list, dtype=object),
                np.array(opens_list, dtype=np.float64),
                np.array(highs_list, dtype=np.float64),
                np.array(lows_list, dtype=np.float64),
                np.array(closes_list, dtype=np.float64),
                np.array(volumes_list, dtype=np.int64)
            )
        finally:
            self._lock = False

    def get_last_close(self) -> Optional[float]:
        """Get the most recent close price"""
        while self._lock:
            pass
        self._lock = True
        try:
            return self.closes[-1] if len(self.closes) > 0 else None
        finally:
            self._lock = False

    def get_last_n_closes(self, n: int) -> np.ndarray:
        """Get last N close prices as numpy array"""
        while self._lock:
            pass
        self._lock = True
        try:
            closes_list = list(self.closes)[-n:] if n > 0 else []
            return np.array(closes_list, dtype=np.float64)
        finally:
            self._lock = False

    def is_ready(self, min_bars: int = 20) -> bool:
        """Check if buffer has enough bars for analysis"""
        return len(self.closes) >= min_bars

    def length(self) -> int:
        """Number of bars in buffer"""
        return len(self.closes)

    def clear(self):
        """Clear all data"""
        self._lock = True
        self.timestamps.clear()
        self.opens.clear()
        self.highs.clear()
        self.lows.clear()
        self.closes.clear()
        self.volumes.clear()
        self._lock = False

    def __repr__(self) -> str:
        last_close = self.get_last_close()
        return f"BarBuffer({self.symbol}, bars={self.length()}, last_close={last_close})"
