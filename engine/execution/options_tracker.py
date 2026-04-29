import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OptionPosition:
    symbol: str
    strategy: str           # "sell_put" or "credit_spread"
    strike: float           # short-leg strike for both strategies
    expiry: str             # "YYYY-MM-DD"
    premium_collected: float  # per-share price at entry
    current_value: float    # current per-share mark
    qty: int                # number of contracts (1 contract = 100 shares)
    upper_strike: Optional[float] = None   # long-leg strike for credit spread
    delta: float = 0.0
    theta: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)

    @property
    def unrealized_pnl(self) -> float:
        # Short premium strategy: profit = (collected - current) × contracts × 100
        return (self.premium_collected - self.current_value) * self.qty * 100

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.premium_collected > 0:
            return (self.premium_collected - self.current_value) / self.premium_collected
        return 0.0

    @property
    def days_to_expiry(self) -> int:
        try:
            exp = datetime.strptime(self.expiry, "%Y-%m-%d")
            return max(0, (exp - datetime.now()).days)
        except Exception:
            return 0


class OptionsTracker:
    """
    Tracks open sell-put and credit-spread option positions.
    Mirrors the PnLTracker interface so the API server can treat both uniformly.
    """

    def __init__(self):
        self.sell_put_positions:      Dict[str, OptionPosition] = {}
        self.credit_spread_positions: Dict[str, OptionPosition] = {}
        self.zero_dte_positions:      Dict[str, OptionPosition] = {}

        self._sp_realized  = 0.0
        self._cs_realized  = 0.0
        self._0dte_realized = 0.0
        self._sp_wins      = 0
        self._sp_losses    = 0
        self._cs_wins      = 0
        self._cs_losses    = 0
        self._0dte_wins    = 0
        self._0dte_losses  = 0

    # ------------------------------------------------------------------ #
    # Position management                                                  #
    # ------------------------------------------------------------------ #

    def open_position(
        self,
        strategy: str,
        symbol: str,
        strike: float,
        expiry: str,
        premium: float,
        qty: int = 1,
        upper_strike: Optional[float] = None,
        delta: float = 0.0,
        theta: float = 0.0,
    ):
        pos = OptionPosition(
            symbol=symbol, strategy=strategy, strike=strike,
            expiry=expiry, premium_collected=premium,
            current_value=premium, qty=qty,
            upper_strike=upper_strike, delta=delta, theta=theta,
        )
        key = self._key(symbol, strike, expiry)
        self._bucket(strategy)[key] = pos
        logger.info(
            f"Opened {strategy} {symbol} strike={strike} exp={expiry} "
            f"premium=${premium:.2f} qty={qty}"
        )

    def update_mark(
        self,
        strategy: str,
        symbol: str,
        strike: float,
        expiry: str,
        current_value: float,
        delta: float = 0.0,
        theta: float = 0.0,
    ):
        key = self._key(symbol, strike, expiry)
        pos = self._bucket(strategy).get(key)
        if pos:
            pos.current_value = current_value
            pos.delta  = delta
            pos.theta  = theta

    def close_position(
        self,
        strategy: str,
        symbol: str,
        strike: float,
        expiry: str,
        close_value: float,
    ):
        key = self._key(symbol, strike, expiry)
        bucket = self._bucket(strategy)
        pos = bucket.pop(key, None)
        if pos is None:
            return
        pnl = (pos.premium_collected - close_value) * pos.qty * 100
        if strategy == "sell_put":
            self._sp_realized += pnl
            if pnl > 0: self._sp_wins    += 1
            else:        self._sp_losses  += 1
        elif strategy == "0dte":
            self._0dte_realized += pnl
            if pnl > 0: self._0dte_wins   += 1
            else:        self._0dte_losses += 1
        else:
            self._cs_realized += pnl
            if pnl > 0: self._cs_wins   += 1
            else:        self._cs_losses += 1
        logger.info(f"Closed {strategy} {symbol} strike={strike}: P&L=${pnl:.2f}")

    # ------------------------------------------------------------------ #
    # Serialisation                                                        #
    # ------------------------------------------------------------------ #

    def get_sell_put_positions(self) -> List[Dict]:
        return [self._to_dict(p) for p in self.sell_put_positions.values()]

    def get_credit_spread_positions(self) -> List[Dict]:
        return [self._to_dict(p) for p in self.credit_spread_positions.values()]

    def get_zero_dte_positions(self) -> List[Dict]:
        return [self._to_dict(p) for p in self.zero_dte_positions.values()]

    def get_sell_put_stats(self) -> Dict:
        return self._stats(
            self.sell_put_positions,
            self._sp_realized,
            self._sp_wins,
            self._sp_losses,
        )

    def get_credit_spread_stats(self) -> Dict:
        return self._stats(
            self.credit_spread_positions,
            self._cs_realized,
            self._cs_wins,
            self._cs_losses,
        )

    def get_zero_dte_stats(self) -> Dict:
        return self._stats(
            self.zero_dte_positions,
            self._0dte_realized,
            self._0dte_wins,
            self._0dte_losses,
        )

    def get_winning_sell_put(self) -> Optional[str]:
        return self._best_symbol(self.sell_put_positions)

    def get_winning_credit_spread(self) -> Optional[str]:
        return self._best_symbol(self.credit_spread_positions)

    def get_winning_zero_dte(self) -> Optional[str]:
        return self._best_symbol(self.zero_dte_positions)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _key(symbol: str, strike: float, expiry: str) -> str:
        return f"{symbol}_{strike}_{expiry}"

    def _bucket(self, strategy: str) -> Dict[str, OptionPosition]:
        if strategy == "sell_put":
            return self.sell_put_positions
        if strategy == "0dte":
            return self.zero_dte_positions
        return self.credit_spread_positions

    @staticmethod
    def _to_dict(p: OptionPosition) -> Dict:
        return {
            "symbol":            p.symbol,
            "strategy":          p.strategy,
            "strike":            p.strike,
            "upper_strike":      p.upper_strike,
            "expiry":            p.expiry,
            "premium_collected": p.premium_collected,
            "current_value":     p.current_value,
            "qty":               p.qty,
            "unrealized_pnl":    round(p.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(p.unrealized_pnl_pct, 4),
            "days_to_expiry":    p.days_to_expiry,
            "delta":             p.delta,
            "theta":             p.theta,
        }

    @staticmethod
    def _stats(
        positions: Dict,
        realized: float,
        wins: int,
        losses: int,
    ) -> Dict:
        unrealized = sum(p.unrealized_pnl for p in positions.values())
        total = wins + losses
        return {
            "realized_pnl":   round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_pnl":      round(realized + unrealized, 2),
            "open_positions": len(positions),
            "win_rate":       round(wins / total, 4) if total > 0 else 0.0,
        }

    @staticmethod
    def _best_symbol(positions: Dict) -> Optional[str]:
        if not positions:
            return None
        best = max(positions.values(), key=lambda p: p.unrealized_pnl)
        return best.symbol if best.unrealized_pnl > 0 else None
