import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.agents.base_agent import BaseAgent
from engine.models.features import build_features, FEATURE_DIM

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    _LGBM_OK = True
except ImportError:
    _LGBM_OK = False
    logger.warning("LightGBM not available — training will be skipped")

# How many bars ahead we look to label a sample
_FORWARD_BARS = 5
# Min price move to be labelled buy (+1) or sell (-1); else hold (0)
_LABEL_THRESHOLD = 0.003


class TrainingAgent(BaseAgent):
    """
    Builds a labelled dataset from real OHLCV bars, trains a LightGBM
    classifier, and exports the result to a versioned ONNX file.
    """

    name = "training_agent"

    async def run(self, dataset: Dict, output_path: str) -> Dict:
        self.logger.info("Building labelled training dataset")

        X_parts, y_parts = [], []
        for sym, bars in dataset.items():
            X, y = self._label(bars)
            if X is not None:
                X_parts.append(X)
                y_parts.append(y)
                dist = np.bincount(y + 1, minlength=3)
                self.logger.info(f"{sym}: {len(y)} samples  sell={dist[0]} hold={dist[1]} buy={dist[2]}")

        if not X_parts:
            result = {"status": "failed", "reason": "no labelled samples generated"}
            await self.publish("training_failed", result)
            return result

        X = np.vstack(X_parts)
        y = np.concatenate(y_parts)

        # Walk-forward split: first 80 % for training, last 20 % for validation
        split = int(0.8 * len(X))
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]
        self.logger.info(f"Train={len(X_tr)}  Val={len(X_val)}")

        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, self._train, X_tr, y_tr + 1, X_val, y_val + 1)

        if model is None:
            result = {"status": "failed", "reason": "LightGBM not installed"}
            await self.publish("training_failed", result)
            return result

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        versioned = str(Path(output_path).parent / f"scalp_{timestamp}.onnx")

        ok = await loop.run_in_executor(None, self._export_onnx, model, versioned)
        if not ok:
            result = {"status": "failed", "reason": "ONNX export failed"}
            await self.publish("training_failed", result)
            return result

        val_preds = model.predict(X_val)
        val_acc = float(np.mean(val_preds == (y_val + 1)))

        result = {
            "status": "success",
            "model_path": versioned,
            "val_accuracy": round(val_acc, 4),
            "train_samples": len(X_tr),
            "val_samples": len(X_val),
        }
        self.logger.info(f"Training complete — val_acc={val_acc:.3f}  path={versioned}")
        await self.publish("training_complete", result)
        return result

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _label(self, bars: Dict) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        opens, highs, lows, closes, volumes = (
            bars["opens"], bars["highs"], bars["lows"],
            bars["closes"], bars["volumes"],
        )
        n = len(closes)
        lookback = 20
        rows_X, rows_y = [], []

        for i in range(lookback, n - _FORWARD_BARS):
            feat = build_features(
                opens[:i+1], highs[:i+1], lows[:i+1],
                closes[:i+1], volumes[:i+1], lookback=lookback,
            )
            if feat is None:
                continue

            fwd = (closes[i + _FORWARD_BARS] - closes[i]) / (closes[i] + 1e-8)
            if fwd >= _LABEL_THRESHOLD:
                label = 1
            elif fwd <= -_LABEL_THRESHOLD:
                label = -1
            else:
                label = 0

            rows_X.append(feat.flatten())
            rows_y.append(label)

        if not rows_X:
            return None, None
        return np.array(rows_X, dtype=np.float32), np.array(rows_y, dtype=np.int32)

    def _train(self, X_tr, y_tr, X_val, y_val):
        if not _LGBM_OK:
            return None

        tr_ds  = lgb.Dataset(X_tr, label=y_tr)
        val_ds = lgb.Dataset(X_val, label=y_val, reference=tr_ds)

        params = {
            "objective":        "multiclass",
            "num_class":        3,
            "metric":           "multi_logloss",
            "boosting_type":    "gbdt",
            "num_leaves":       63,
            "learning_rate":    0.05,
            "min_child_samples": 20,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq":     5,
            "verbose":          -1,
        }
        callbacks = [
            lgb.early_stopping(stopping_rounds=25, verbose=False),
            lgb.log_evaluation(period=50),
        ]
        return lgb.train(
            params, tr_ds,
            num_boost_round=400,
            valid_sets=[val_ds],
            callbacks=callbacks,
        )

    def _export_onnx(self, model, output_path: str) -> bool:
        try:
            import onnxmltools
            from onnxmltools.convert.common.data_types import FloatTensorType

            initial_type = [("float_input", FloatTensorType([None, FEATURE_DIM]))]
            onnx_model = onnxmltools.convert_lightgbm(model, initial_types=initial_type)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            onnxmltools.utils.save_model(onnx_model, output_path)
            self.logger.info(f"ONNX saved → {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"ONNX export error: {e}")
            return False
