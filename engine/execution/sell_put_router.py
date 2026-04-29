"""
Sell Put Router

On a bullish signal (+1) with sufficient confidence, sells a slightly OTM weekly put
on configured symbols, collecting premium upfront.

Entry:  signal +1, confidence >= 0.60 → sell put at ~95% of current price
Expiry: next Friday that is >= 7 DTE
Exit:   50% of max profit retained  OR  cost-to-close = 2× premium  OR  DTE <= 1

Paper mode: when PAPER_OPTIONS_SIM=true, bypasses Alpaca order submission and
simulates theta decay locally so iOS stats populate during development.
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import httpx

from engine.broker.alpaca_client import AlpacaClient
from engine.config import settings
from engine.execution.options_tracker import OptionsTracker
from engine.execution.options_utils import next_weekly_expiry, occ_symbol
from engine.execution.risk import RiskManager

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.60
_STRIKE_PCT_OTM = 0.95    # sell put 5% below spot, rounded to nearest $5
_PROFIT_TARGET  = 0.50    # close when 50% of premium is retained as profit
_STOP_MULT      = 2.0     # close when cost-to-close reaches 2× entry premium
_DTE_EXIT       = 1       # hard close with ≤1 day to expiry
_MAX_CONTRACTS  = 1
_MIN_PREMIUM    = 0.10
_POLL_INTERVAL  = 300     # seconds between position checks
_COOLDOWN_SECS  = 600     # per-symbol cooldown between entries
_SIM_DECAY_MINS = 120.0   # paper sim: premium decays to ~5% over this many minutes


class SellPutRouter:
    """Routes bullish signals into short (naked) weekly put positions."""

    def __init__(
        self,
        alpaca: AlpacaClient,
        options_tracker: OptionsTracker,
        risk: RiskManager,
        symbols: Optional[List[str]] = None,
    ):
        self.alpaca  = alpaca
        self.tracker = options_tracker
        self.risk    = risk
        self._symbols: List[str] = list(symbols or [])
        self._last_entry: Dict[str, datetime] = {}
        self._active: Dict[str, asyncio.Task] = {}
        self._data_client = httpx.AsyncClient(
            base_url=settings.alpaca_data_url,
            headers={
                "APCA-API-KEY-ID":     settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            },
            timeout=10.0,
        )

    def set_symbols(self, symbols: List[str]):
        self._symbols = [s.strip().upper() for s in symbols]
        logger.info(f"SellPutRouter symbols: {self._symbols}")

    async def route_signal(self, symbol: str, signal: int, price: float, confidence: float):
        if symbol not in self._symbols or signal != 1:
            return
        if confidence < _MIN_CONFIDENCE:
            return

        now = datetime.now()
        last = self._last_entry.get(symbol)
        if last and (now - last).total_seconds() < _COOLDOWN_SECS:
            return

        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"SellPut: risk block {symbol} — {reason}")
            return

        expiry = next_weekly_expiry()
        strike = round(price * _STRIKE_PCT_OTM / 5) * 5.0
        premium = await self._get_premium(symbol, expiry, strike)

        if premium < _MIN_PREMIUM:
            logger.info(f"SellPut: {symbol} premium ${premium:.2f} below minimum, skip")
            return

        if not await self._submit_or_sim(symbol, expiry, strike, premium):
            return

        self.tracker.open_position(
            strategy="sell_put",
            symbol=symbol,
            strike=strike,
            expiry=expiry.isoformat(),
            premium=premium,
            qty=_MAX_CONTRACTS,
        )
        self._last_entry[symbol] = now
        logger.info(
            f"SellPut opened: {symbol} P{strike} exp={expiry} "
            f"premium=${premium:.2f} ({_MAX_CONTRACTS}c)"
        )

        key = f"{symbol}_{strike}_{expiry.isoformat()}"
        self._active[key] = asyncio.create_task(
            self._monitor(key, symbol, strike, expiry, premium, now)
        )

    async def close_all(self):
        for task in list(self._active.values()):
            task.cancel()
        self._active.clear()

    async def aclose(self):
        await self._data_client.aclose()

    # ------------------------------------------------------------------ #
    # Pricing helpers                                                      #
    # ------------------------------------------------------------------ #

    async def _get_premium(self, symbol: str, expiry: date, strike: float) -> float:
        try:
            occ = occ_symbol(symbol, expiry, "PUT", strike)
            resp = await self._data_client.get(
                f"/v1beta1/options/snapshots/{symbol}",
                params={
                    "feed":            "indicative",
                    "expiration_date": expiry.isoformat(),
                    "type":            "put",
                    "limit":           50,
                },
            )
            resp.raise_for_status()
            snap = resp.json().get("snapshots", {}).get(occ, {})
            q = snap.get("latestQuote", {})
            bid = float(q.get("bp", 0) or 0)
            ask = float(q.get("ap", 0) or 0)
            if bid > 0 or ask > 0:
                return (bid + ask) / 2
        except Exception as e:
            logger.debug(f"SellPut: chain fetch failed ({e}), using synthetic")
        return round(strike * 0.015, 2)

    async def _current_value(self, symbol: str, expiry: date, strike: float) -> Optional[float]:
        try:
            occ = occ_symbol(symbol, expiry, "PUT", strike)
            resp = await self._data_client.get(
                "/v1beta1/options/snapshots",
                params={"symbols": occ, "feed": "indicative"},
            )
            resp.raise_for_status()
            snap = resp.json().get("snapshots", {}).get(occ, {})
            q = snap.get("latestQuote", {})
            bid = float(q.get("bp", 0) or 0)
            ask = float(q.get("ap", 0) or 0)
            return (bid + ask) / 2 if (bid > 0 or ask > 0) else None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Order submission / paper simulation                                  #
    # ------------------------------------------------------------------ #

    async def _submit_or_sim(
        self, symbol: str, expiry: date, strike: float, premium: float
    ) -> bool:
        if settings.is_paper and settings.paper_options_sim:
            logger.info(
                f"SellPut [PAPER SIM]: {symbol} P{strike} exp={expiry} "
                f"premium=${premium:.2f} — simulated fill"
            )
            return True

        occ = occ_symbol(symbol, expiry, "PUT", strike)
        body = {
            "symbol":        occ,
            "qty":           str(_MAX_CONTRACTS),
            "side":          "sell",
            "type":          "limit",
            "limit_price":   str(round(premium, 2)),
            "time_in_force": "day",
        }
        try:
            resp = await self.alpaca.http_client.post("/v2/orders", json=body)
            if resp.status_code in (200, 201):
                logger.info(f"SellPut order submitted: {occ} → {resp.json().get('id')}")
                return True
            logger.error(f"SellPut order rejected ({resp.status_code}): {resp.json()}")
            return False
        except Exception as e:
            logger.error(f"SellPut submit error: {e}")
            return False

    async def _close_order(
        self, symbol: str, expiry: date, strike: float, close_value: float
    ):
        if settings.is_paper and settings.paper_options_sim:
            return
        occ = occ_symbol(symbol, expiry, "PUT", strike)
        body = {
            "symbol":        occ,
            "qty":           str(_MAX_CONTRACTS),
            "side":          "buy",
            "type":          "limit",
            "limit_price":   str(round(close_value, 2)),
            "time_in_force": "day",
        }
        try:
            resp = await self.alpaca.http_client.post("/v2/orders", json=body)
            if resp.status_code not in (200, 201):
                logger.error(f"SellPut close rejected ({resp.status_code}): {resp.json()}")
        except Exception as e:
            logger.error(f"SellPut close error: {e}")

    # ------------------------------------------------------------------ #
    # Position monitor                                                     #
    # ------------------------------------------------------------------ #

    async def _monitor(
        self,
        key: str,
        symbol: str,
        strike: float,
        expiry: date,
        entry_premium: float,
        entry_dt: datetime,
    ):
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)

                days_left = (expiry - date.today()).days
                if days_left <= _DTE_EXIT:
                    close_val = await self._current_value(symbol, expiry, strike) or entry_premium * 0.05
                    logger.info(f"SellPut: {key} DTE={days_left}, time-exit at ${close_val:.2f}")
                    await self._do_close(key, symbol, strike, expiry, entry_premium, close_val)
                    return

                if settings.is_paper and settings.paper_options_sim:
                    elapsed_min = (datetime.now() - entry_dt).total_seconds() / 60
                    current = entry_premium * max(0.05, 1.0 - elapsed_min / _SIM_DECAY_MINS)
                else:
                    current = await self._current_value(symbol, expiry, strike)
                    if current is None:
                        continue

                self.tracker.update_mark("sell_put", symbol, strike, expiry.isoformat(), current)

                profit_pct = 1.0 - (current / entry_premium) if entry_premium > 0 else 0.0
                if profit_pct >= _PROFIT_TARGET:
                    logger.info(f"SellPut: profit target {profit_pct:.0%}, closing {key}")
                    await self._do_close(key, symbol, strike, expiry, entry_premium, current)
                    return

                if current >= entry_premium * _STOP_MULT:
                    logger.warning(f"SellPut: stop loss hit (${current:.2f} vs entry ${entry_premium:.2f}), closing {key}")
                    await self._do_close(key, symbol, strike, expiry, entry_premium, current)
                    return

        except asyncio.CancelledError:
            logger.info(f"SellPut monitor cancelled: {key}")
        except Exception as e:
            logger.error(f"SellPut monitor error {key}: {e}", exc_info=True)
        finally:
            self._active.pop(key, None)

    async def _do_close(
        self,
        key: str,
        symbol: str,
        strike: float,
        expiry: date,
        entry_premium: float,
        close_value: float,
    ):
        await self._close_order(symbol, expiry, strike, close_value)
        self.tracker.close_position(
            strategy="sell_put",
            symbol=symbol,
            strike=strike,
            expiry=expiry.isoformat(),
            close_value=close_value,
        )
