import numpy as np
from typing import Optional

FEATURE_DIM = 20


def build_features(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 20,
) -> Optional[np.ndarray]:
    """
    Build a 20-dim feature vector from OHLCV bars.
    Identical logic used at training time and inference time.

    Layout (total = 20):
      [0:9]   log returns of last 9 bars             (momentum)
      [9:14]  high-low / close for last 5 bars       (local volatility)
      [14:19] volume / 20-bar mean for last 5 bars   (relative activity)
      [19]    (close[-1] - SMA20) / SMA20            (trend position)
    """
    if len(closes) < lookback:
        return None

    c = closes[-lookback:].astype(np.float64)
    h = highs[-lookback:].astype(np.float64)
    l = lows[-lookback:].astype(np.float64)
    v = volumes[-lookback:].astype(np.float64)

    returns = np.diff(np.log(c + 1e-8))        # 19 values
    feat_returns = returns[-9:]                  # last 9

    hl_ratio = (h - l) / (c + 1e-8)
    feat_hl = hl_ratio[-5:]                      # last 5

    mean_vol = np.mean(v) + 1e-8
    feat_vol = (v / mean_vol)[-5:]               # last 5

    sma = np.mean(c)
    feat_trend = np.array([(c[-1] - sma) / (sma + 1e-8)])  # 1 value

    features = np.concatenate([feat_returns, feat_hl, feat_vol, feat_trend])
    return features.astype(np.float32).reshape(1, FEATURE_DIM)
