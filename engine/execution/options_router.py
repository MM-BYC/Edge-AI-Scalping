"""
0DTE SPY Credit Spread Router

Uses the ensemble signal to enter a same-day credit spread on SPY:
  signal +1 (bullish) → bull put spread  (sell OTM put, buy lower put)
  signal -1 (bearish) → bear call spread (sell OTM call, buy higher call)

Target: 50% of max profit OR 30-minute max hold. Stop at 2× credit received.
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Dict, Optional, Tuple

import httpx

from engine.broker.alpaca_client import AlpacaClient
from engine.config import settings
from engine.execution.options_tracker import OptionsTracker
from engine.execution.risk import RiskManager

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE   = 0.60   # minimum signal confidence to trade
_SPREAD_WIDTH     = 5      # points between the two legs
_MAX_CONTRACTS    = 1      # contracts per signal (scale up later)
_PROFIT_TARGET    = 0.50   # close when 50% of credit retained as profit
_STOP_MULT        = 2.0    # close when cost-to-close = 2× credit received
_MAX_HOLD_SECS    = 1800   # 30-minute hard exit
_COOLDOWN_SECS    = 300    # 5-minute cooldown between new entries
_MIN_CREDIT       = 0.10   # skip if net credit < $0.10/share ($10/contract)
_POLL_INTERVAL    = 60     # check position every 60 seconds


def _occ_symbol(underlying: str, expiry: date, option_type: str, strike: float) -> str:
    """Encode an OCC option symbol, e.g. SPY240429P00500000"""
    date_str  = expiry.strftime("%y%m%d")
    cp        = "C" if option_type.upper() == "CALL" else "P"
    strike_i  = round(strike * 1000)
    return f"{underlying}{date_str}{cp}{strike_i:08d}"


class ZeroDTERouter:
    """Routes high-confidence SPY ensemble signals into 0DTE credit spreads."""

    def __init__(
        self,
        alpaca: AlpacaClient,
        options_tracker: OptionsTracker,
        risk: RiskManager,
    ):
        self.alpaca  = alpaca
        self.tracker = options_tracker
        self.risk    = risk

        self._last_entry: Optional[datetime] = None
        self._active: Dict[str, asyncio.Task] = {}

        self._data_client = httpx.AsyncClient(
            base_url=settings.alpaca_data_url,
            headers={
                "APCA-API-KEY-ID":     settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            },
            timeout=10.0,
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def route_signal(self, signal: int, spy_price: float, confidence: float):
        """
        Called from TradingBot._on_new_bar for SPY bars.
        Ignores hold signal and low-confidence signals.
        """
        if signal == 0:
            return
        if confidence < _MIN_CONFIDENCE:
            logger.debug(f"0DTE: conf {confidence:.2%} below {_MIN_CONFIDENCE:.0%}, skip")
            return

        now = datetime.now()
        if self._last_entry and (now - self._last_entry).total_seconds() < _COOLDOWN_SECS:
            logger.debug("0DTE: cooldown active, skip")
            return

        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            logger.warning(f"0DTE: risk block — {reason}")
            return

        today       = date.today()
        option_type = "PUT" if signal == 1 else "CALL"

        try:
            short_strike, long_strike, credit = await self._select_strikes(
                spy_price, today, option_type
            )
        except Exception as e:
            logger.error(f"0DTE: strike selection failed: {e}")
            return

        if credit < _MIN_CREDIT:
            logger.info(f"0DTE: credit ${credit:.2f} below minimum, skip")
            return

        qty   = _MAX_CONTRACTS
        order = await self._submit_spread(today, option_type, short_strike, long_strike, credit, qty)
        if order is None:
            return

        self.tracker.open_position(
            strategy="0dte",
            symbol="SPY",
            strike=short_strike,
            expiry=today.isoformat(),
            premium=credit,
            qty=qty,
            upper_strike=long_strike,
        )
        self._last_entry = now

        logger.info(
            f"0DTE {option_type} spread: short={short_strike} long={long_strike} "
            f"credit=${credit:.2f}/sh ({qty} contract, max profit ${credit * qty * 100:.0f})"
        )

        key  = f"SPY_{short_strike}_{today.isoformat()}"
        task = asyncio.create_task(
            self._monitor(key, short_strike, long_strike, today, option_type, credit, qty)
        )
        self._active[key] = task

    async def close_all(self):
        """Cancel all active monitor tasks (called on bot shutdown)."""
        for task in list(self._active.values()):
            task.cancel()
        self._active.clear()

    async def aclose(self):
        await self._data_client.aclose()

    # ------------------------------------------------------------------ #
    # Strike selection                                                     #
    # ------------------------------------------------------------------ #

    async def _select_strikes(
        self, spy_price: float, expiry: date, option_type: str
    ) -> Tuple[float, float, float]:
        """
        Fetch the 0DTE options chain snapshot and pick near-ATM strikes.
        Falls back to synthetic pricing if chain unavailable.
        """
        try:
            resp = await self._data_client.get(
                f"/v1beta1/options/snapshots/SPY",
                params={
                    "feed":            "indicative",
                    "expiration_date": expiry.isoformat(),
                    "type":            option_type.lower(),
                    "limit":           200,
                },
            )
            resp.raise_for_status()
            snapshots = resp.json().get("snapshots", {})
        except Exception as e:
            logger.warning(f"0DTE: chain fetch failed ({e}), using synthetic fallback")
            return self._synthetic_strikes(spy_price, option_type)

        if not snapshots:
            logger.warning("0DTE: empty chain response, using synthetic fallback")
            return self._synthetic_strikes(spy_price, option_type)

        chain = self._parse_chain(snapshots)
        if not chain:
            return self._synthetic_strikes(spy_price, option_type)

        return self._pick_strikes(chain, spy_price, option_type)

    def _parse_chain(self, snapshots: dict) -> list:
        """Convert snapshot dict to sorted list of (strike, mid)."""
        rows = []
        for occ_sym, snap in snapshots.items():
            try:
                q   = snap.get("latestQuote", {})
                bid = float(q.get("bp", 0) or 0)
                ask = float(q.get("ap", 0) or 0)
                mid = (bid + ask) / 2
                if mid <= 0:
                    continue
                # Strike is encoded as last 8 chars × 0.001
                strike = int(occ_sym[-8:]) / 1000.0
                rows.append((strike, mid))
            except Exception:
                continue
        rows.sort()
        return rows

    def _pick_strikes(
        self, chain: list, spy_price: float, option_type: str
    ) -> Tuple[float, float, float]:
        if option_type == "PUT":
            # Bull put: sell slightly below spot, buy _SPREAD_WIDTH lower
            target_short = spy_price * 0.99
            puts_below   = [(s, m) for s, m in chain if s <= spy_price]
            if not puts_below:
                return self._synthetic_strikes(spy_price, option_type)
            short_s, short_m = min(puts_below, key=lambda x: abs(x[0] - target_short))
            long_s  = short_s - _SPREAD_WIDTH
            long_m  = self._nearest_mid(chain, long_s)
            credit  = max(0.0, short_m - long_m)
        else:
            # Bear call: sell slightly above spot, buy _SPREAD_WIDTH higher
            target_short = spy_price * 1.01
            calls_above  = [(s, m) for s, m in chain if s >= spy_price]
            if not calls_above:
                return self._synthetic_strikes(spy_price, option_type)
            short_s, short_m = min(calls_above, key=lambda x: abs(x[0] - target_short))
            long_s  = short_s + _SPREAD_WIDTH
            long_m  = self._nearest_mid(chain, long_s)
            credit  = max(0.0, short_m - long_m)

        return short_s, long_s, credit

    @staticmethod
    def _nearest_mid(chain: list, target_strike: float) -> float:
        """Return the mid price of the option closest to target_strike."""
        if not chain:
            return 0.0
        _, mid = min(chain, key=lambda x: abs(x[0] - target_strike))
        return mid

    @staticmethod
    def _synthetic_strikes(spy_price: float, option_type: str) -> Tuple[float, float, float]:
        """Fallback strikes rounded to the nearest $5."""
        if option_type == "PUT":
            short = round(spy_price * 0.99 / 5) * 5
            long  = short - _SPREAD_WIDTH
        else:
            short = round(spy_price * 1.01 / 5) * 5
            long  = short + _SPREAD_WIDTH
        logger.warning(f"0DTE: synthetic strikes short={short} long={long}")
        return float(short), float(long), 0.15

    # ------------------------------------------------------------------ #
    # Order submission                                                     #
    # ------------------------------------------------------------------ #

    async def _submit_spread(
        self,
        expiry:       date,
        option_type:  str,
        short_strike: float,
        long_strike:  float,
        credit:       float,
        qty:          int,
    ) -> Optional[Dict]:
        short_sym = _occ_symbol("SPY", expiry, option_type, short_strike)
        long_sym  = _occ_symbol("SPY", expiry, option_type, long_strike)

        body = {
            "type":          "limit",
            "time_in_force": "day",
            "order_class":   "multileg",
            "limit_price":   str(round(credit, 2)),
            "legs": [
                {"symbol": short_sym, "side": "sell", "qty": str(qty), "position_intent": "open"},
                {"symbol": long_sym,  "side": "buy",  "qty": str(qty), "position_intent": "open"},
            ],
        }
        try:
            resp   = await self.alpaca.http_client.post("/v2/orders", json=body)
            result = resp.json()
            if resp.status_code in (200, 201):
                logger.info(f"0DTE order submitted {short_sym}/{long_sym} → {result.get('id')}")
                return result
            logger.error(f"0DTE order rejected ({resp.status_code}): {result}")
            return None
        except Exception as e:
            logger.error(f"0DTE submit error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Position monitoring                                                  #
    # ------------------------------------------------------------------ #

    async def _monitor(
        self,
        key:          str,
        short_strike: float,
        long_strike:  float,
        expiry:       date,
        option_type:  str,
        entry_credit: float,
        qty:          int,
    ):
        """Poll every 60s; exit on profit target, stop loss, or max hold time."""
        short_sym = _occ_symbol("SPY", expiry, option_type, short_strike)
        long_sym  = _occ_symbol("SPY", expiry, option_type, long_strike)
        deadline  = asyncio.get_event_loop().time() + _MAX_HOLD_SECS

        try:
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(_POLL_INTERVAL)

                cost = await self._spread_cost(short_sym, long_sym)
                if cost is None:
                    continue

                profit_pct = 1.0 - (cost / entry_credit) if entry_credit > 0 else 0.0

                if profit_pct >= _PROFIT_TARGET:
                    logger.info(f"0DTE profit target hit ({profit_pct:.0%}), closing {key}")
                    await self._close_spread(key, short_sym, long_sym, qty, cost, short_strike, expiry, entry_credit)
                    return

                if cost >= entry_credit * _STOP_MULT:
                    logger.warning(f"0DTE stop loss hit (cost ${cost:.2f} vs entry ${entry_credit:.2f}), closing {key}")
                    await self._close_spread(key, short_sym, long_sym, qty, cost, short_strike, expiry, entry_credit)
                    return

            # Max hold time reached
            cost = await self._spread_cost(short_sym, long_sym) or entry_credit
            logger.info(f"0DTE max hold time reached, closing {key}")
            await self._close_spread(key, short_sym, long_sym, qty, cost, short_strike, expiry, entry_credit)

        except asyncio.CancelledError:
            logger.info(f"0DTE monitor cancelled: {key}")
        except Exception as e:
            logger.error(f"0DTE monitor error for {key}: {e}", exc_info=True)
        finally:
            self._active.pop(key, None)

    async def _spread_cost(self, short_sym: str, long_sym: str) -> Optional[float]:
        """Current mid-price cost to buy back the spread (debit to close)."""
        try:
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
        except Exception as e:
            logger.warning(f"0DTE: quote poll failed: {e}")
            return None

    async def _close_spread(
        self,
        key:          str,
        short_sym:    str,
        long_sym:     str,
        qty:          int,
        close_cost:   float,
        short_strike: float,
        expiry:       date,
        entry_credit: float,
    ):
        body = {
            "type":          "limit",
            "time_in_force": "day",
            "order_class":   "multileg",
            "limit_price":   str(round(close_cost, 2)),
            "legs": [
                {"symbol": short_sym, "side": "buy",  "qty": str(qty), "position_intent": "close"},
                {"symbol": long_sym,  "side": "sell", "qty": str(qty), "position_intent": "close"},
            ],
        }
        try:
            resp   = await self.alpaca.http_client.post("/v2/orders", json=body)
            result = resp.json()
            if resp.status_code in (200, 201):
                logger.info(f"0DTE close submitted → {result.get('id')}")
            else:
                logger.error(f"0DTE close rejected ({resp.status_code}): {result}")
        except Exception as e:
            logger.error(f"0DTE close error: {e}")

        self.tracker.close_position(
            strategy="0dte",
            symbol="SPY",
            strike=short_strike,
            expiry=expiry.isoformat(),
            close_value=close_cost,
        )
