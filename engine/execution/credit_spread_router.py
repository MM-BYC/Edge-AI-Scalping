"""
Credit Spread Router (Weekly)

Routes directional signals into weekly credit spreads:
  signal +1 (bullish) → bull put spread  (sell OTM put,  buy lower put)
  signal -1 (bearish) → bear call spread (sell OTM call, buy higher call)

Expiry: next Friday >= 7 DTE
Width:  $5 between legs
Exit:   50% of max profit  OR  2× credit stop  OR  DTE <= 1

Paper mode: when PAPER_OPTIONS_SIM=true, bypasses Alpaca order submission and
simulates theta decay locally so iOS stats populate during development.
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import httpx

from engine.broker.alpaca_client import AlpacaClient
from engine.config import settings
from engine.execution.options_tracker import OptionsTracker
from engine.execution.options_utils import next_weekly_expiry, occ_symbol
from engine.execution.risk import RiskManager

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.60
_SPREAD_WIDTH   = 5.0
_PROFIT_TARGET  = 0.50
_STOP_MULT      = 2.0
_DTE_EXIT       = 1
_MAX_CONTRACTS  = 1
_MIN_CREDIT     = 0.10
_POLL_INTERVAL  = 300
_COOLDOWN_SECS  = 600
_SIM_DECAY_MINS = 120.0


class CreditSpreadRouter:
    """Routes directional signals into weekly bull-put or bear-call credit spreads."""

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
        logger.info(f"CreditSpreadRouter symbols: {self._symbols}")

    async def route_signal(self, symbol: str, signal: int, price: float, confidence: float):
        if symbol not in self._symbols or signal == 0:
            return
        if confidence < _MIN_CONFIDENCE:
            return

        now = datetime.now()
        last = self._last_entry.get(symbol)
        if last and (now - last).total_seconds() < _COOLDOWN_SECS:
            return

        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"CreditSpread: risk block {symbol} — {reason}")
            return

        expiry = next_weekly_expiry()
        option_type = "PUT" if signal == 1 else "CALL"

        short_strike, long_strike, credit = await self._select_strikes(
            symbol, price, expiry, option_type
        )
        if credit < _MIN_CREDIT:
            logger.info(f"CreditSpread: {symbol} credit ${credit:.2f} below minimum, skip")
            return

        if not await self._submit_or_sim(symbol, expiry, option_type, short_strike, long_strike, credit):
            return

        self.tracker.open_position(
            strategy="credit_spread",
            symbol=symbol,
            strike=short_strike,
            expiry=expiry.isoformat(),
            premium=credit,
            qty=_MAX_CONTRACTS,
            upper_strike=long_strike,
        )
        self._last_entry[symbol] = now
        logger.info(
            f"CreditSpread opened: {symbol} {option_type} short={short_strike} "
            f"long={long_strike} exp={expiry} credit=${credit:.2f}"
        )

        key = f"{symbol}_{option_type}_{short_strike}_{expiry.isoformat()}"
        self._active[key] = asyncio.create_task(
            self._monitor(key, symbol, option_type, short_strike, long_strike, expiry, credit, now)
        )

    async def close_all(self):
        for task in list(self._active.values()):
            task.cancel()
        self._active.clear()

    async def aclose(self):
        await self._data_client.aclose()

    # ------------------------------------------------------------------ #
    # Strike selection                                                     #
    # ------------------------------------------------------------------ #

    async def _select_strikes(
        self, symbol: str, price: float, expiry: date, option_type: str
    ) -> Tuple[float, float, float]:
        try:
            resp = await self._data_client.get(
                f"/v1beta1/options/snapshots/{symbol}",
                params={
                    "feed":            "indicative",
                    "expiration_date": expiry.isoformat(),
                    "type":            option_type.lower(),
                    "limit":           200,
                },
            )
            resp.raise_for_status()
            snapshots = resp.json().get("snapshots", {})
            if snapshots:
                chain = self._parse_chain(snapshots)
                if chain:
                    return self._pick_strikes(chain, price, option_type)
        except Exception as e:
            logger.debug(f"CreditSpread: chain fetch failed ({e}), using synthetic")

        return self._synthetic_strikes(price, option_type)

    @staticmethod
    def _parse_chain(snapshots: dict) -> list:
        rows = []
        for occ_sym, snap in snapshots.items():
            try:
                q = snap.get("latestQuote", {})
                bid = float(q.get("bp", 0) or 0)
                ask = float(q.get("ap", 0) or 0)
                mid = (bid + ask) / 2
                if mid <= 0:
                    continue
                strike = int(occ_sym[-8:]) / 1000.0
                rows.append((strike, mid))
            except Exception:
                continue
        rows.sort()
        return rows

    @staticmethod
    def _pick_strikes(
        chain: list, price: float, option_type: str
    ) -> Tuple[float, float, float]:
        def nearest_mid(target: float) -> Tuple[float, float]:
            return min(chain, key=lambda x: abs(x[0] - target))

        if option_type == "PUT":
            target_short = price * 0.99
            candidates = [(s, m) for s, m in chain if s <= price]
            if not candidates:
                return CreditSpreadRouter._synthetic_strikes(price, option_type)
            short_s, short_m = min(candidates, key=lambda x: abs(x[0] - target_short))
            long_s = short_s - _SPREAD_WIDTH
            _, long_m = nearest_mid(long_s)
            credit = max(0.0, short_m - long_m)
        else:
            target_short = price * 1.01
            candidates = [(s, m) for s, m in chain if s >= price]
            if not candidates:
                return CreditSpreadRouter._synthetic_strikes(price, option_type)
            short_s, short_m = min(candidates, key=lambda x: abs(x[0] - target_short))
            long_s = short_s + _SPREAD_WIDTH
            _, long_m = nearest_mid(long_s)
            credit = max(0.0, short_m - long_m)

        return short_s, long_s, credit

    @staticmethod
    def _synthetic_strikes(price: float, option_type: str) -> Tuple[float, float, float]:
        if option_type == "PUT":
            short = round(price * 0.99 / 5) * 5.0
            long  = short - _SPREAD_WIDTH
        else:
            short = round(price * 1.01 / 5) * 5.0
            long  = short + _SPREAD_WIDTH
        credit = 0.20
        logger.debug(f"CreditSpread: synthetic strikes short={short} long={long}")
        return float(short), float(long), credit

    # ------------------------------------------------------------------ #
    # Order submission / paper simulation                                  #
    # ------------------------------------------------------------------ #

    async def _submit_or_sim(
        self,
        symbol: str,
        expiry: date,
        option_type: str,
        short_strike: float,
        long_strike: float,
        credit: float,
    ) -> bool:
        if settings.is_paper and settings.paper_options_sim:
            logger.info(
                f"CreditSpread [PAPER SIM]: {symbol} {option_type} "
                f"short={short_strike} long={long_strike} exp={expiry} "
                f"credit=${credit:.2f} — simulated fill"
            )
            return True

        short_sym = occ_symbol(symbol, expiry, option_type, short_strike)
        long_sym  = occ_symbol(symbol, expiry, option_type, long_strike)
        body = {
            "type":          "limit",
            "time_in_force": "day",
            "order_class":   "multileg",
            "limit_price":   str(round(credit, 2)),
            "legs": [
                {"symbol": short_sym, "side": "sell", "qty": str(_MAX_CONTRACTS), "position_intent": "open"},
                {"symbol": long_sym,  "side": "buy",  "qty": str(_MAX_CONTRACTS), "position_intent": "open"},
            ],
        }
        try:
            resp = await self.alpaca.http_client.post("/v2/orders", json=body)
            if resp.status_code in (200, 201):
                logger.info(f"CreditSpread order submitted → {resp.json().get('id')}")
                return True
            logger.error(f"CreditSpread order rejected ({resp.status_code}): {resp.json()}")
            return False
        except Exception as e:
            logger.error(f"CreditSpread submit error: {e}")
            return False

    async def _close_order(
        self,
        symbol: str,
        expiry: date,
        option_type: str,
        short_strike: float,
        long_strike: float,
        cost: float,
    ):
        if settings.is_paper and settings.paper_options_sim:
            return
        short_sym = occ_symbol(symbol, expiry, option_type, short_strike)
        long_sym  = occ_symbol(symbol, expiry, option_type, long_strike)
        body = {
            "type":          "limit",
            "time_in_force": "day",
            "order_class":   "multileg",
            "limit_price":   str(round(cost, 2)),
            "legs": [
                {"symbol": short_sym, "side": "buy",  "qty": str(_MAX_CONTRACTS), "position_intent": "close"},
                {"symbol": long_sym,  "side": "sell", "qty": str(_MAX_CONTRACTS), "position_intent": "close"},
            ],
        }
        try:
            resp = await self.alpaca.http_client.post("/v2/orders", json=body)
            if resp.status_code not in (200, 201):
                logger.error(f"CreditSpread close rejected ({resp.status_code}): {resp.json()}")
        except Exception as e:
            logger.error(f"CreditSpread close error: {e}")

    async def _spread_cost(
        self, symbol: str, expiry: date, option_type: str, short_strike: float, long_strike: float
    ) -> Optional[float]:
        try:
            short_sym = occ_symbol(symbol, expiry, option_type, short_strike)
            long_sym  = occ_symbol(symbol, expiry, option_type, long_strike)
            resp = await self._data_client.get(
                "/v1beta1/options/snapshots",
                params={"symbols": f"{short_sym},{long_sym}", "feed": "indicative"},
            )
            resp.raise_for_status()
            snaps = resp.json().get("snapshots", {})

            def mid(sym: str) -> Optional[float]:
                q = snaps.get(sym, {}).get("latestQuote", {})
                b = float(q.get("bp", 0) or 0)
                a = float(q.get("ap", 0) or 0)
                return (b + a) / 2 if (b > 0 or a > 0) else None

            s_mid = mid(short_sym)
            l_mid = mid(long_sym)
            if s_mid is None or l_mid is None:
                return None
            return max(0.0, s_mid - l_mid)
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Position monitor                                                     #
    # ------------------------------------------------------------------ #

    async def _monitor(
        self,
        key: str,
        symbol: str,
        option_type: str,
        short_strike: float,
        long_strike: float,
        expiry: date,
        entry_credit: float,
        entry_dt: datetime,
    ):
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)

                days_left = (expiry - date.today()).days
                if days_left <= _DTE_EXIT:
                    close_cost = entry_credit * 0.05
                    logger.info(f"CreditSpread: {key} DTE={days_left}, time-exit at ${close_cost:.2f}")
                    await self._do_close(key, symbol, option_type, short_strike, long_strike, expiry, entry_credit, close_cost)
                    return

                if settings.is_paper and settings.paper_options_sim:
                    elapsed_min = (datetime.now() - entry_dt).total_seconds() / 60
                    cost = entry_credit * max(0.05, 1.0 - elapsed_min / _SIM_DECAY_MINS)
                else:
                    cost = await self._spread_cost(symbol, expiry, option_type, short_strike, long_strike)
                    if cost is None:
                        continue

                self.tracker.update_mark("credit_spread", symbol, short_strike, expiry.isoformat(), cost)

                profit_pct = 1.0 - (cost / entry_credit) if entry_credit > 0 else 0.0
                if profit_pct >= _PROFIT_TARGET:
                    logger.info(f"CreditSpread: profit target {profit_pct:.0%}, closing {key}")
                    await self._do_close(key, symbol, option_type, short_strike, long_strike, expiry, entry_credit, cost)
                    return

                if cost >= entry_credit * _STOP_MULT:
                    logger.warning(f"CreditSpread: stop hit (${cost:.2f} vs ${entry_credit:.2f}), closing {key}")
                    await self._do_close(key, symbol, option_type, short_strike, long_strike, expiry, entry_credit, cost)
                    return

        except asyncio.CancelledError:
            logger.info(f"CreditSpread monitor cancelled: {key}")
        except Exception as e:
            logger.error(f"CreditSpread monitor error {key}: {e}", exc_info=True)
        finally:
            self._active.pop(key, None)

    async def _do_close(
        self,
        key: str,
        symbol: str,
        option_type: str,
        short_strike: float,
        long_strike: float,
        expiry: date,
        entry_credit: float,
        close_cost: float,
    ):
        await self._close_order(symbol, expiry, option_type, short_strike, long_strike, close_cost)
        self.tracker.close_position(
            strategy="credit_spread",
            symbol=symbol,
            strike=short_strike,
            expiry=expiry.isoformat(),
            close_value=close_cost,
        )
