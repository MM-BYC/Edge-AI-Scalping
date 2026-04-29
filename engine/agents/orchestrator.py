import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

from engine.agents.base_agent import AgentMessage
from engine.agents.data_agent import DataAgent
from engine.agents.training_agent import TrainingAgent
from engine.agents.eval_agent import EvalAgent
from engine.agents.deploy_agent import DeployAgent
from engine.config import settings
from engine.models.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class RetrainingOrchestrator:
    """
    Nightly multi-agent retraining pipeline.

    Execution order
    ───────────────
    DataAgent   →  fetches real bars for all symbols concurrently
    TrainingAgent  →  builds labelled dataset, trains LightGBM, exports ONNX
    EvalAgent   →  runs new model and current model against holdout in parallel
    DeployAgent →  deploys if model improves; penalises ensemble weights if not

    The shared asyncio.Queue lets any agent broadcast events that other
    components (e.g. the API server) can subscribe to in the future.
    """

    def __init__(self, ensemble=None):
        self.ensemble  = ensemble
        self.registry  = ModelRegistry()
        self.bus: asyncio.Queue = asyncio.Queue()

        self.data_agent     = DataAgent(self.bus)
        self.training_agent = TrainingAgent(self.bus)
        self.eval_agent     = EvalAgent(self.bus)
        self.deploy_agent   = DeployAgent(
            self.bus,
            self.registry,
            live_model_path=str(settings.model_path_full),
            ensemble=self.ensemble,
        )

    async def run(self) -> Optional[Dict]:
        t0 = datetime.now()
        logger.info("━━━  Nightly Retraining Pipeline  START  ━━━")
        logger.info(f"Registry: {self.registry.summary()}")

        lookback = getattr(settings, "retrain_lookback_days", 90)
        symbols  = settings.symbols_list

        # ── 1. Fetch bars (symbols fetched in parallel inside DataAgent) ──
        dataset = await self.data_agent.run(symbols=symbols, lookback_days=lookback)
        if not dataset:
            logger.error("No market data returned — aborting retraining")
            return None

        # ── 2. Split chronologically: 80 % train / 20 % holdout ──────────
        train_ds, holdout_ds = _split_dataset(dataset, frac=0.8)

        # ── 3. Train ──────────────────────────────────────────────────────
        train_result = await self.training_agent.run(
            dataset=train_ds,
            output_path=str(settings.model_path_full),
        )
        if train_result["status"] != "success":
            logger.error(f"Training failed: {train_result.get('reason')}")
            return None

        # ── 4. Eval (new vs current run concurrently inside EvalAgent) ────
        eval_result = await self.eval_agent.run(
            new_model_path=train_result["model_path"],
            current_model_path=(
                str(settings.model_path_full)
                if self.registry.current_model else None
            ),
            holdout=holdout_ds,
        )

        # ── 5. Deploy or penalise ─────────────────────────────────────────
        deploy_result = await self.deploy_agent.run(eval_result)

        elapsed = (datetime.now() - t0).total_seconds()
        status  = "DEPLOYED" if deploy_result["deployed"] else f"REJECTED — {deploy_result.get('reason', '')}"
        logger.info(f"━━━  Pipeline DONE in {elapsed:.1f}s  [{status}]  ━━━")
        return deploy_result

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    async def drain_bus(self):
        """Drain any unconsumed bus messages (useful for tests)."""
        while not self.bus.empty():
            msg: AgentMessage = self.bus.get_nowait()
            logger.debug(f"bus: [{msg.topic}] from {msg.sender}")


def _split_dataset(dataset: Dict, frac: float = 0.8):
    train_ds: Dict = {}
    hold_ds:  Dict = {}
    for sym, bars in dataset.items():
        n     = len(bars["closes"])
        split = int(n * frac)
        train_ds[sym] = {k: v[:split] for k, v in bars.items() if hasattr(v, "__len__")}
        hold_ds[sym]  = {k: v[split:] for k, v in bars.items() if hasattr(v, "__len__")}
    return train_ds, hold_ds
