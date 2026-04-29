import asyncio
import logging
import shutil
from typing import Dict, Optional

from engine.agents.base_agent import BaseAgent
from engine.models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

# Minimum absolute win-rate improvement over the current model
_MIN_WIN_RATE_IMPROVEMENT = 0.01   # 1 pp
# New model must be at least mildly profitable on its own
_MIN_PROFIT_FACTOR = 1.05


class DeployAgent(BaseAgent):
    """
    Decides whether to deploy or reject a newly trained model.

    Deploy criteria (both must pass):
      1. profit_factor >= 1.05  (model is net-positive on holdout)
      2. win_rate > current_win_rate + 1 pp  (or no current model)

    On rejection the registry increases the failure streak, which reduces
    the ensemble ML weight — giving more influence back to the rule-based
    signal until a good model is found.
    """

    name = "deploy_agent"

    def __init__(
        self,
        bus: asyncio.Queue,
        registry: ModelRegistry,
        live_model_path: str,
        ensemble=None,
    ):
        super().__init__(bus)
        self.registry = registry
        self.live_model_path = live_model_path
        self.ensemble = ensemble

    async def run(self, eval_result: Dict) -> Dict:
        new_m   = eval_result["new_metrics"]
        curr_m  = eval_result.get("current_metrics")
        new_path = eval_result["new_model_path"]

        rejection_reason = self._check_gates(new_m, curr_m)

        if rejection_reason:
            self.logger.warning(f"Model rejected: {rejection_reason}")
            self.registry.record_rejection(new_m, rejection_reason, prev_metrics=curr_m)
            self._apply_weights()
            result = {"deployed": False, "reason": rejection_reason, "metrics": new_m}
        else:
            shutil.copy2(new_path, self.live_model_path)
            self.registry.record_deployment(new_path, new_m, prev_metrics=curr_m)
            self.logger.info(f"Model deployed: {new_path} → {self.live_model_path}")
            self._apply_weights()
            result = {"deployed": True, "model_path": self.live_model_path, "metrics": new_m}

        await self.publish("deploy_result", result)
        return result

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _check_gates(self, new_m: Dict, curr_m: Optional[Dict]) -> Optional[str]:
        if new_m["profit_factor"] < _MIN_PROFIT_FACTOR:
            return (
                f"profit_factor {new_m['profit_factor']:.3f} < "
                f"required {_MIN_PROFIT_FACTOR}"
            )
        if curr_m is not None:
            delta = new_m["win_rate"] - curr_m["win_rate"]
            if delta < _MIN_WIN_RATE_IMPROVEMENT:
                return (
                    f"win_rate improvement {delta:+.3f} < "
                    f"required {_MIN_WIN_RATE_IMPROVEMENT}"
                )
        return None

    def _apply_weights(self):
        if self.ensemble is None:
            return
        ml_w   = self.registry.ml_weight
        rule_w = 1.0 - ml_w
        self.ensemble.update_weights(rule_weight=rule_w, ml_weight=ml_w)
        self.logger.info(f"Ensemble weights updated: rules={rule_w:.2f} ml={ml_w:.2f}")
        if hasattr(self.ensemble, "reload_model"):
            self.ensemble.reload_model(self.live_model_path)
