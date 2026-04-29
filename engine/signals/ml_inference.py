import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
import logging
import time

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
        """
        Preprocess raw OHLCV data into model features
        Features: normalized OHLCV, returns, volatility, volume ratio
        """
        if len(closes) < lookback:
            return None

        try:
            # Get last lookback bars
            closes_slice = closes[-lookback:].astype(np.float64)
            opens_slice = opens[-lookback:].astype(np.float64)
            highs_slice = highs[-lookback:].astype(np.float64)
            lows_slice = lows[-lookback:].astype(np.float64)
            volumes_slice = volumes[-lookback:].astype(np.float64)

            features = []

            # Normalized OHLCV (0-1 scale per bar)
            for i in range(lookback):
                close_normalized = closes_slice[i] / (closes_slice[i] + 1e-8)
                features.append(close_normalized)

            # Price returns (log returns)
            returns = np.diff(np.log(closes_slice + 1e-8))
            features.extend(returns.tolist())

            # High-Low ratio (volatility proxy)
            hl_ratio = (highs_slice - lows_slice) / (closes_slice + 1e-8)
            features.extend(hl_ratio.tolist())

            # Volume ratio (normalized)
            mean_vol = np.mean(volumes_slice) + 1e-8
            vol_ratio = volumes_slice / mean_vol
            features.extend(vol_ratio.tolist())

            # Pad or truncate to exactly 20 features
            features = features[:20]
            while len(features) < 20:
                features.append(0.0)

            # Reshape for model input [1, 20]
            features_array = np.array(features, dtype=np.float32).reshape(1, 20)

            return features_array

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

    def is_available(self) -> bool:
        """Check if model is ready for inference"""
        return self.model_loaded and ONNX_AVAILABLE
