import numpy as np
import pandas_ta as ta
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Vectorized technical indicator calculations"""

    @staticmethod
    def rsi(closes: np.ndarray, length: int = 14) -> Optional[float]:
        """Calculate RSI, return latest value"""
        if len(closes) < length + 1:
            return None
        try:
            rsi_vals = ta.rsi(closes, length=length)
            return float(rsi_vals.iloc[-1]) if rsi_vals is not None else None
        except Exception as e:
            logger.warning(f"RSI calculation error: {e}")
            return None

    @staticmethod
    def macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate MACD, return (macd, signal_line, histogram)"""
        if len(closes) < slow + signal:
            return None, None, None
        try:
            macd_vals = ta.macd(closes, fast=fast, slow=slow, signal=signal)
            if macd_vals is not None and len(macd_vals) > 0:
                macd_line = float(macd_vals.iloc[-1, 0]) if macd_vals.shape[1] > 0 else None
                signal_line = float(macd_vals.iloc[-1, 1]) if macd_vals.shape[1] > 1 else None
                histogram = float(macd_vals.iloc[-1, 2]) if macd_vals.shape[1] > 2 else None
                return macd_line, signal_line, histogram
        except Exception as e:
            logger.warning(f"MACD calculation error: {e}")
        return None, None, None

    @staticmethod
    def vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> Optional[float]:
        """Calculate VWAP, return latest value"""
        if len(closes) < 2:
            return None
        try:
            vwap_vals = ta.vwap(highs, lows, closes, volumes)
            return float(vwap_vals.iloc[-1]) if vwap_vals is not None else None
        except Exception as e:
            logger.warning(f"VWAP calculation error: {e}")
            return None

    @staticmethod
    def volume_delta(volumes: np.ndarray, length: int = 20) -> Optional[float]:
        """Calculate volume delta (ratio of recent to average volume)"""
        if len(volumes) < length:
            return None
        try:
            recent_vol = volumes[-1]
            avg_vol = np.mean(volumes[-length:])
            return float(recent_vol / avg_vol) if avg_vol > 0 else None
        except Exception as e:
            logger.warning(f"Volume delta calculation error: {e}")
            return None

    @staticmethod
    def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, length: int = 14) -> Optional[float]:
        """Calculate ATR, return latest value"""
        if len(closes) < length + 1:
            return None
        try:
            atr_vals = ta.atr(highs, lows, closes, length=length)
            return float(atr_vals.iloc[-1]) if atr_vals is not None else None
        except Exception as e:
            logger.warning(f"ATR calculation error: {e}")
            return None

    @staticmethod
    def sma(closes: np.ndarray, length: int = 20) -> Optional[float]:
        """Calculate SMA, return latest value"""
        if len(closes) < length:
            return None
        try:
            sma_vals = ta.sma(closes, length=length)
            return float(sma_vals.iloc[-1]) if sma_vals is not None else None
        except Exception as e:
            logger.warning(f"SMA calculation error: {e}")
            return None

    @staticmethod
    def ema(closes: np.ndarray, length: int = 20) -> Optional[float]:
        """Calculate EMA, return latest value"""
        if len(closes) < length:
            return None
        try:
            ema_vals = ta.ema(closes, length=length)
            return float(ema_vals.iloc[-1]) if ema_vals is not None else None
        except Exception as e:
            logger.warning(f"EMA calculation error: {e}")
            return None


class RuleBasedSignals:
    """Rule-based trading signal generation"""

    def __init__(self):
        self.indicators = TechnicalIndicators()

    def generate_signal(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> Tuple[int, Dict[str, Optional[float]]]:
        """
        Generate signal from technical indicators
        Returns: (signal, indicator_dict) where signal in {-1, 0, 1}
        -1 = sell, 0 = hold, 1 = buy
        """

        indicators = {}

        # RSI: overbought > 70, oversold < 30
        rsi = self.indicators.rsi(closes)
        indicators["rsi"] = rsi

        # MACD: bullish if MACD > signal, bearish if MACD < signal
        macd, macd_signal, macd_hist = self.indicators.macd(closes)
        indicators["macd"] = macd
        indicators["macd_signal"] = macd_signal
        indicators["macd_hist"] = macd_hist

        # VWAP: price above VWAP is bullish
        vwap = self.indicators.vwap(highs, lows, closes, volumes)
        indicators["vwap"] = vwap

        # Volume delta: increasing volume supports trend
        vol_delta = self.indicators.volume_delta(volumes)
        indicators["volume_delta"] = vol_delta

        # ATR: volatility measure
        atr = self.indicators.atr(highs, lows, closes)
        indicators["atr"] = atr

        # EMAs for trend
        ema_20 = self.indicators.ema(closes, length=20)
        ema_50 = self.indicators.ema(closes, length=50) if len(closes) >= 50 else None
        indicators["ema_20"] = ema_20
        indicators["ema_50"] = ema_50

        # Signal generation logic (simplified for demo)
        signal = 0
        buy_count = 0
        sell_count = 0

        if rsi is not None:
            if rsi < 30:
                buy_count += 1
            elif rsi > 70:
                sell_count += 1

        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                buy_count += 1
            else:
                sell_count += 1

        if vwap is not None and len(closes) > 0:
            if closes[-1] > vwap:
                buy_count += 1
            else:
                sell_count += 1

        if ema_20 is not None and ema_50 is not None:
            if closes[-1] > ema_20 > ema_50:
                buy_count += 1
            elif closes[-1] < ema_20 < ema_50:
                sell_count += 1

        if buy_count > sell_count:
            signal = 1
        elif sell_count > buy_count:
            signal = -1

        return signal, indicators
