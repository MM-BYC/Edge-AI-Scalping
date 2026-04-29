import asyncio
import logging
from collections import deque
from typing import Optional

from engine.agents.base_agent import BaseAgent
from engine.models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

_WINDOW          = 20    # rolling closed-trade window
_CHECK_INTERVAL  = 60    # seconds between polls
_MIN_TRADES      = 5     # don't act until this many trades are in the window
_TRIGGER         = 0.05  # divergence threshold (5 pp) before nudging
_NUDGE           = 0.03  # weight change per adjustment step
_MAX_DRIFT       = 0.10  # max deviation from the nightly registry baseline


class LiveFeedbackAgent(BaseAgent):
    """
    Watches live closed-trade outcomes every 60 seconds and makes small,
    bounded intraday adjustments to the ensemble's ML weight.

    How it works
    ────────────
    • Polls PnLTracker.get_stats() each interval to detect new wins/losses.
    • Maintains a rolling deque of the last 20 trade outcomes (1=win, 0=loss).
    • Compares the recent win-rate against the last deployed model's holdout
      win-rate (the nightly baseline).
    • If the live model is underperforming by > 5 pp → nudge ML weight down.
    • If overperforming by > 5 pp → nudge ML weight up.
    • Weight is clamped so it can never drift more than ±MAX_DRIFT from the
      nightly registry value — preventing intraday noise from permanently
      overriding the trained model.
    • On daily reset (pnl_tracker.reset_daily called) the window is cleared
      and tracking restarts clean.
    • At 16:15 ET the nightly orchestrator always calls _apply_weights(),
      which resets the ensemble to the registry value regardless of intraday
      drift.
    """

    name = "live_feedback_agent"

    def __init__(self, bus: asyncio.Queue, registry: ModelRegistry, pnl_tracker, ensemble):
        super().__init__(bus)
        self.registry    = registry
        self.pnl_tracker = pnl_tracker
        self.ensemble    = ensemble

        self._outcomes: deque = deque(maxlen=_WINDOW)
        self._prev_wins   = 0
        self._prev_losses = 0
        self._running     = False

    async def start(self):
        self._running = True
        self.logger.info(
            f"LiveFeedbackAgent started "
            f"(window={_WINDOW} trades, interval={_CHECK_INTERVAL}s, "
            f"trigger=±{_TRIGGER:.0%}, max_drift=±{_MAX_DRIFT:.0%})"
        )
        while self._running:
            await asyncio.sleep(_CHECK_INTERVAL)
            if self._running:
                await self._check()

    def stop(self):
        self._running = False
        self.logger.info("LiveFeedbackAgent stopped")

    # ------------------------------------------------------------------ #
    # Core check                                                           #
    # ------------------------------------------------------------------ #

    async def _check(self):
        stats  = self.pnl_tracker.get_stats()
        wins   = stats["winning_trades"]
        losses = stats["losing_trades"]

        # Detect daily reset (pnl_tracker.reset_daily zeroes the counters)
        if wins < self._prev_wins or losses < self._prev_losses:
            self.logger.info("Daily reset detected — clearing intraday window")
            self._outcomes.clear()
            self._prev_wins = self._prev_losses = 0

        # Ingest new outcomes since last check
        new_wins   = wins   - self._prev_wins
        new_losses = losses - self._prev_losses
        self._prev_wins   = wins
        self._prev_losses = losses

        for _ in range(new_wins):
            self._outcomes.append(1)
        for _ in range(new_losses):
            self._outcomes.append(0)

        n_trades = len(self._outcomes)
        if n_trades < _MIN_TRADES:
            self.logger.debug(f"LiveFeedback: only {n_trades}/{_MIN_TRADES} trades — waiting")
            return

        # Compute recent win-rate and compare to nightly baseline
        recent_wr    = sum(self._outcomes) / n_trades
        baseline_m   = self.registry.get_last_deployed_metrics()
        baseline_wr  = baseline_m["win_rate"] if baseline_m else 0.5
        nightly_w    = self.registry.ml_weight
        current_w    = self.ensemble.ml_weight
        delta        = recent_wr - baseline_wr

        new_w, action = self._decide(delta, nightly_w, current_w)

        if new_w != current_w:
            self.ensemble.update_weights(rule_weight=1.0 - new_w, ml_weight=new_w)

        payload = {
            "recent_win_rate":  round(recent_wr,   4),
            "baseline_win_rate": round(baseline_wr, 4),
            "delta":            round(delta,        4),
            "ml_weight":        round(new_w,        4),
            "trades_in_window": n_trades,
            "action":           action,
        }
        await self.publish("live_feedback", payload)
        self.logger.info(
            f"LiveFeedback: recent={recent_wr:.3f} baseline={baseline_wr:.3f} "
            f"Δ={delta:+.3f} trades={n_trades} → {action}"
        )

    # ------------------------------------------------------------------ #
    # Decision logic                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _decide(delta: float, nightly_w: float, current_w: float):
        """
        Returns (new_weight, action_label).

        Boundaries:
          lower = nightly_w - MAX_DRIFT   (floor — won't strip ML entirely intraday)
          upper = nightly_w + MAX_DRIFT   (ceiling — won't over-trust ML intraday)
        """
        floor   = max(0.0, nightly_w - _MAX_DRIFT)
        ceiling = min(1.0, nightly_w + _MAX_DRIFT)

        if delta < -_TRIGGER:
            # Live performance worse than nightly baseline → reduce ML weight
            new_w  = max(floor, current_w - _NUDGE)
            action = f"penalise ▼ {current_w:.3f}→{new_w:.3f} (live Δ={delta:+.3f})"
        elif delta > _TRIGGER:
            # Live performance better than nightly baseline → increase ML weight
            new_w  = min(ceiling, current_w + _NUDGE)
            action = f"reward  ▲ {current_w:.3f}→{new_w:.3f} (live Δ={delta:+.3f})"
        else:
            new_w  = current_w
            action = f"hold {current_w:.3f} (live Δ={delta:+.3f}, within ±{_TRIGGER:.0%})"

        return new_w, action
