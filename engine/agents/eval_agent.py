import asyncio
import logging
import random
from typing import Dict, Optional

import numpy as np

from engine.agents.base_agent import BaseAgent
from engine.models.features import build_features

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    _ONNX_OK = True
except ImportError:
    _ONNX_OK = False

_FORWARD_BARS      = 5
_LABEL_THRESHOLD   = 0.003
_PRECHECK_FRAC     = 0.10   # 10% sample for the fast gate check
_PRECHECK_MIN_PTS  = 100    # floor so the sample is never statistically empty
_PROFIT_FACTOR_GATE = 1.05  # must match deploy_agent._MIN_PROFIT_FACTOR


class EvalAgent(BaseAgent):
    """
    Evaluates new and current ONNX models against a held-out dataset.

    Short-circuit logic
    ───────────────────
    Before running either full evaluation, a fast pre-check runs the new
    model over a random 10% sample of the holdout.  If it fails the
    profit-factor gate immediately, the current model is never evaluated
    and the result is returned right away — saving roughly 90% of eval
    time for bad models (which will be the common case early in training).

    When the pre-check passes, both the new and current model evaluations
    run in parallel on the full holdout via asyncio.gather.
    """

    name = "eval_agent"

    async def run(
        self,
        new_model_path: str,
        current_model_path: Optional[str],
        holdout: Dict,
    ) -> Dict:
        loop = asyncio.get_event_loop()

        # ── Fast pre-check on new model (10 % sample) ────────────────────
        self.logger.info("Pre-check: sampling 10% of holdout on new model")
        precheck = await loop.run_in_executor(
            None, self._eval, new_model_path, holdout, _PRECHECK_FRAC
        )
        self.logger.info(
            f"Pre-check: profit_factor={precheck['profit_factor']:.3f} "
            f"signals={precheck['total_signals']}"
        )

        if precheck["profit_factor"] < _PROFIT_FACTOR_GATE:
            self.logger.info(
                f"Pre-check FAILED (profit_factor={precheck['profit_factor']:.3f} "
                f"< {_PROFIT_FACTOR_GATE}) — skipping full eval"
            )
            result = {
                "new_model_path":     new_model_path,
                "current_model_path": current_model_path,
                "new_metrics":        precheck,
                "current_metrics":    None,
                "short_circuited":    True,
            }
            await self.publish("eval_complete", result)
            return result

        # ── Full eval: new and current run in parallel ────────────────────
        self.logger.info("Pre-check passed — running full eval on both models")
        new_task = loop.run_in_executor(
            None, self._eval, new_model_path, holdout, 1.0
        )
        curr_task = (
            loop.run_in_executor(None, self._eval, current_model_path, holdout, 1.0)
            if current_model_path
            else _null_coro()
        )
        new_metrics, current_metrics = await asyncio.gather(new_task, curr_task)

        self.logger.info(f"New:     {new_metrics}")
        self.logger.info(f"Current: {current_metrics}")

        result = {
            "new_model_path":     new_model_path,
            "current_model_path": current_model_path,
            "new_metrics":        new_metrics,
            "current_metrics":    current_metrics,
            "short_circuited":    False,
        }
        await self.publish("eval_complete", result)
        return result

    # ------------------------------------------------------------------ #
    # Simulation kernel                                                    #
    # ------------------------------------------------------------------ #

    def _eval(self, model_path: str, dataset: Dict, sample_frac: float = 1.0) -> Dict:
        if not _ONNX_OK:
            return {"win_rate": 0.5, "profit_factor": 1.0, "total_signals": 0}

        try:
            sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            inp  = sess.get_inputs()[0].name
            out  = sess.get_outputs()[0].name
        except Exception as e:
            self.logger.error(f"Cannot load {model_path}: {e}")
            return {"win_rate": 0.0, "profit_factor": 0.0, "total_signals": 0}

        wins = losses = signals = 0
        gross_profit = gross_loss = 0.0
        rng = random.Random(42)

        for bars in dataset.values():
            c, o, h, l, v = (
                bars["closes"], bars["opens"], bars["highs"],
                bars["lows"],   bars["volumes"],
            )
            n = len(c)
            all_indices = list(range(20, n - _FORWARD_BARS))
            if not all_indices:
                continue

            if sample_frac < 1.0:
                k       = max(_PRECHECK_MIN_PTS, int(len(all_indices) * sample_frac))
                indices = rng.sample(all_indices, min(k, len(all_indices)))
            else:
                indices = all_indices

            for i in indices:
                feat = build_features(o[:i+1], h[:i+1], l[:i+1], c[:i+1], v[:i+1])
                if feat is None:
                    continue

                raw   = sess.run([out], {inp: feat})[0][0]
                probs = np.exp(raw - raw.max())
                probs /= probs.sum()
                signal = int(np.argmax(probs)) - 1   # {0,1,2} → {-1,0,1}

                if signal == 0:
                    continue

                fwd       = (c[i + _FORWARD_BARS] - c[i]) / (c[i] + 1e-8)
                trade_ret = signal * fwd
                signals  += 1

                if trade_ret > 0:
                    wins         += 1
                    gross_profit += trade_ret
                else:
                    losses    += 1
                    gross_loss += abs(trade_ret)

        win_rate = wins / signals if signals else 0.0
        pf = (
            gross_profit / gross_loss if gross_loss > 0
            else (1.0 if gross_profit > 0 else 0.0)
        )
        return {
            "win_rate":      round(win_rate, 4),
            "profit_factor": round(pf, 4),
            "total_signals": signals,
            "wins":          wins,
            "losses":        losses,
        }


async def _null_coro():
    """Awaitable that returns None (replaces deprecated asyncio.coroutine)."""
    return None
