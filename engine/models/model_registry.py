import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "registry.json"

_DEFAULT_ML_WEIGHT = 0.6
_MIN_ML_WEIGHT     = 0.0

# Win-rate changes smaller than this are treated as "unchanged" (no reward/penalty)
_UNCHANGED_EPSILON = 0.005   # 0.5 pp

# Reward scaling: proportional to win-rate improvement (pp → weight delta)
_REWARD_PER_PP = 0.15        # 1 pp improvement → +0.015 weight; ~7 pp → +0.10
_MIN_REWARD    = 0.05        # floor so even small gains register
_MAX_REWARD    = 0.20        # cap so one great run doesn't dominate

# Penalty multipliers per failure in the current streak
_PENALTY_MILD  = 0.05        # win rate flat or barely moved — didn't improve enough
_PENALTY_HARD  = 0.20        # win rate actually decreased — hard penalise


class ModelRegistry:
    """
    Tracks deployed model versions, per-run metrics, and the ML ensemble weight.

    Reward / penalty rules
    ──────────────────────
    Deployed — win-rate delta vs previous model:
      ▲ increased (> 0.5 pp)  → reward proportional to delta, capped at +0.20
      ≈ unchanged (≤ 0.5 pp)  → no change to weight
      ▼ decreased (shouldn't  → mild penalty (deploy gate blocks this, but defensive)
         reach here after gate)

    Rejected — win-rate delta vs previous model:
      ▼ decreased             → HARD penalty × streak (model got worse, punish)
      ≈ flat or small gain    → mild penalty × streak (stalled, keep pressure on)

    Persisted as JSON at engine/models/registry.json.
    """

    def __init__(self, path: Path = REGISTRY_PATH):
        self.path  = path
        self._data = self._load()

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def current_model(self) -> Optional[str]:
        return self._data.get("current_model")

    @property
    def ml_weight(self) -> float:
        return self._data.get("ml_weight", _DEFAULT_ML_WEIGHT)

    @property
    def consecutive_failures(self) -> int:
        return self._data.get("consecutive_failures", 0)

    # ------------------------------------------------------------------ #
    # Mutation                                                             #
    # ------------------------------------------------------------------ #

    def record_deployment(
        self,
        model_path: str,
        metrics: Dict,
        prev_metrics: Optional[Dict] = None,
    ):
        """
        Record a successful deployment.  Reward is proportional to win-rate
        improvement; no reward if win rate is unchanged.
        """
        self._data["current_model"]       = model_path
        self._data["consecutive_failures"] = 0

        delta = _win_rate_delta(metrics, prev_metrics)
        old_w = self._data.get("ml_weight", _DEFAULT_ML_WEIGHT)

        if delta is None or abs(delta) <= _UNCHANGED_EPSILON:
            # First model ever, or no meaningful change — hold weight steady
            new_w   = old_w
            verdict = "no change (first deploy or flat win-rate)"
        elif delta > _UNCHANGED_EPSILON:
            reward  = _clamp(_REWARD_PER_PP * delta * 100, _MIN_REWARD, _MAX_REWARD)
            new_w   = min(_DEFAULT_ML_WEIGHT, old_w + reward)
            verdict = f"rewarded +{reward:.3f} (win-rate Δ={delta:+.3f})"
        else:
            # delta < -epsilon: model regressed after passing gates (defensive path)
            new_w   = max(_MIN_ML_WEIGHT, old_w - _PENALTY_MILD)
            verdict = f"mild penalty (win-rate Δ={delta:+.3f})"

        self._data["ml_weight"] = round(new_w, 4)
        self._data.setdefault("history", []).append({
            "timestamp":  datetime.now().isoformat(),
            "model_path": model_path,
            "deployed":   True,
            "win_rate_delta": delta,
            "metrics":    metrics,
            "prev_metrics": prev_metrics,
        })
        self._save()
        logger.info(f"Registry deployed {model_path}: {verdict} → ml_weight={new_w:.3f}")

    def record_rejection(
        self,
        metrics: Dict,
        reason: str,
        prev_metrics: Optional[Dict] = None,
    ):
        """
        Record a rejected model.  Penalty severity depends on whether the
        win rate actually went down (hard) or merely stalled (mild).
        """
        self._data["consecutive_failures"] = self._data.get("consecutive_failures", 0) + 1
        streak = self._data["consecutive_failures"]

        delta = _win_rate_delta(metrics, prev_metrics)
        old_w = self._data.get("ml_weight", _DEFAULT_ML_WEIGHT)

        if delta is not None and delta < -_UNCHANGED_EPSILON:
            # Win rate decreased — hard penalty that scales with streak
            penalty = _PENALTY_HARD * streak
            verdict = f"HARD penalty ×{streak} (win-rate Δ={delta:+.3f})"
        else:
            # Win rate flat or insufficient improvement — mild escalating penalty
            penalty = _PENALTY_MILD * streak
            verdict = f"mild penalty ×{streak} (win-rate Δ={delta:+.3f if delta is not None else 'n/a'})"

        new_w = max(_MIN_ML_WEIGHT, old_w - penalty)
        self._data["ml_weight"] = round(new_w, 4)
        self._data.setdefault("history", []).append({
            "timestamp":  datetime.now().isoformat(),
            "deployed":   False,
            "reason":     reason,
            "win_rate_delta": delta,
            "metrics":    metrics,
            "prev_metrics": prev_metrics,
        })
        self._save()
        logger.warning(
            f"Registry rejected ({reason}): {verdict} → ml_weight={new_w:.3f}"
        )

    def get_last_deployed_metrics(self) -> Optional[Dict]:
        for entry in reversed(self._data.get("history", [])):
            if entry.get("deployed"):
                return entry.get("metrics")
        return None

    def summary(self) -> Dict:
        return {
            "current_model":       self.current_model,
            "ml_weight":           self.ml_weight,
            "consecutive_failures": self.consecutive_failures,
            "total_runs":          len(self._data.get("history", [])),
        }

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read registry, starting fresh: {e}")
        return {
            "current_model":       None,
            "ml_weight":           _DEFAULT_ML_WEIGHT,
            "consecutive_failures": 0,
            "history":             [],
        }

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)


# ------------------------------------------------------------------ #
# Module-level helpers                                                #
# ------------------------------------------------------------------ #

def _win_rate_delta(new_m: Dict, prev_m: Optional[Dict]) -> Optional[float]:
    """Return new_win_rate − prev_win_rate, or None if there is no baseline."""
    if prev_m is None:
        return None
    return new_m.get("win_rate", 0.0) - prev_m.get("win_rate", 0.0)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
