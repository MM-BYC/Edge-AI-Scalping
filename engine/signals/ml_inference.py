import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
import logging
import time

from engine.models.features import build_features, FEATURE_DIM  # shared feature pipeline

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logger.warning("onnxruntime not installed, ML inference disabled")


class MLModelInference:
    """ONNX model inference wrapper for scalping signals"""

    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.session: Optional[ort.InferenceSession] = None
        self.input_name: Optional[str] = None
        self.output_name: Optional[str] = None
        self.model_loaded = False

        if ONNX_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """Load ONNX model from disk"""
        if not self.model_path.exists():
            logger.warning(f"Model file not found: {self.model_path}")
            return

        try:
            # Use CoreML execution provider on Apple Silicon for faster inference
            providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=providers,
                sess_options=self._get_session_options()
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.model_loaded = True
            logger.info(f"ML model loaded: {self.model_path}")
            logger.info(f"Using providers: {self.session.get_providers()}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model_loaded = False

    def _get_session_options(self) -> ort.SessionOptions:
        """Configure session for performance"""
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.inter_op_num_threads = 2
        opts.intra_op_num_threads = 2
        return opts

    def preprocess_features(self, closes: np.ndarray, opens: np.ndarray, highs: np.ndarray,
                           lows: np.ndarray, volumes: np.ndarray, lookback: int = 20) -> Optional[np.ndarray]:
        """Delegate to the shared feature pipeline (same logic used at training time)."""
        try:
            return build_features(opens, highs, lows, closes, volumes, lookback=lookback)
        except Exception as e:
            logger.error(f"Feature preprocessing error: {e}")
            return None

    def predict(self, features: np.ndarray) -> Tuple[Optional[int], Optional[float], float]:
        """
        Predict signal using ML model
        Returns: (signal, confidence, inference_time_ms)
        signal: -1 (sell), 0 (hold), 1 (buy), None if error
        """
        if not self.model_loaded or features is None:
            return None, None, 0.0

        try:
            start_time = time.perf_counter()

            # Run inference
            outputs = self.session.run([self.output_name], {self.input_name: features})
            logits = outputs[0][0]  # [num_classes]

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Convert logits to probabilities
            exp_logits = np.exp(logits - np.max(logits))
            probs = exp_logits / np.sum(exp_logits)

            # Get predicted class and confidence
            signal = np.argmax(probs) - 1  # 0->-1, 1->0, 2->1
            confidence = float(np.max(probs))

            logger.debug(f"ML inference: signal={signal}, confidence={confidence:.3f}, time={elapsed_ms:.2f}ms")

            return signal, confidence, elapsed_ms

        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return None, None, 0.0

    def batch_predict(self, features_list: List[np.ndarray]) -> List[Tuple[Optional[int], Optional[float]]]:
        """Predict multiple feature sets at once (for parallel symbols)"""
        results = []
        for features in features_list:
            signal, confidence, _ = self.predict(features)
            results.append((signal, confidence))
        return results

    def reload_model(self, new_path: str):
        """Hot-swap the ONNX session with a freshly deployed model."""
        self.model_path = Path(new_path)
        self.session = None
        self.model_loaded = False
        if ONNX_AVAILABLE:
            self._load_model()
        if self.model_loaded:
            logger.info(f"Model hot-reloaded: {new_path}")
        else:
            logger.error(f"Hot-reload failed for: {new_path}")

    def is_available(self) -> bool:
        """Check if model is ready for inference"""
        return self.model_loaded and ONNX_AVAILABLE
