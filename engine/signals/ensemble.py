import numpy as np
from typing import Tuple, Dict, Optional
import logging

from engine.signals.rules import RuleBasedSignals
from engine.signals.ml_inference import MLModelInference

logger = logging.getLogger(__name__)


class SignalEnsemble:
    """Weighted ensemble of rule-based and ML signals"""

    def __init__(self, ml_model_path: str, rule_weight: float = 0.4, ml_weight: float = 0.6):
        """
        Initialize ensemble
        rule_weight: importance of technical rules (0-1)
        ml_weight: importance of ML model (0-1)
        """
        self.rules = RuleBasedSignals()
        self.ml_model = MLModelInference(ml_model_path)
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight

        # Normalize weights
        total = rule_weight + ml_weight
        self.rule_weight = rule_weight / total
        self.ml_weight = ml_weight / total

        logger.info(f"SignalEnsemble: rules={self.rule_weight:.1%}, ml={self.ml_weight:.1%}")

    def generate_signal(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray
    ) -> Tuple[int, Dict]:
        """
        Generate ensemble signal
        Returns: (signal, analysis_dict)
        signal: -1 (strong sell), 0 (hold), 1 (strong buy)
        """

        analysis = {
            "rule_signal": None,
            "rule_indicators": {},
            "ml_signal": None,
            "ml_confidence": None,
            "ml_inference_time_ms": 0.0,
            "ensemble_signal": 0,
            "ensemble_confidence": 0.0,
            "ready": False
        }

        # Minimum bars check
        if len(closes) < 20:
            analysis["ready"] = False
            return 0, analysis

        analysis["ready"] = True

        # Get rule-based signal
        rule_signal, indicators = self.rules.generate_signal(opens, highs, lows, closes, volumes)
        analysis["rule_signal"] = rule_signal
        analysis["rule_indicators"] = indicators

        # Get ML signal (if model available)
        ml_signal = None
        ml_confidence = None
        ml_inference_time = 0.0

        if self.ml_model.is_available():
            features = self.ml_model.preprocess_features(closes, opens, highs, lows, volumes)
            if features is not None:
                ml_signal, ml_confidence, ml_inference_time = self.ml_model.predict(features)
                analysis["ml_signal"] = ml_signal
                analysis["ml_confidence"] = ml_confidence
                analysis["ml_inference_time_ms"] = ml_inference_time

        # Ensemble voting
        if ml_signal is not None and ml_confidence is not None:
            # Weighted ensemble: combine both signals
            rule_contribution = rule_signal * self.rule_weight
            ml_contribution = ml_signal * self.ml_weight * (ml_confidence ** 0.5)  # Weight by confidence

            ensemble_score = rule_contribution + ml_contribution
            ensemble_signal = int(np.sign(ensemble_score))
            ensemble_confidence = min(1.0, abs(ensemble_score))

            logger.debug(
                f"Ensemble: rule={rule_signal} ({self.rule_weight:.1%}) + "
                f"ml={ml_signal} ({self.ml_weight:.1%}, conf={ml_confidence:.2f}) "
                f"-> {ensemble_signal} (confidence={ensemble_confidence:.2f})"
            )
        else:
            # Fall back to rules only if ML not available
            ensemble_signal = rule_signal
            ensemble_confidence = 0.5  # Default moderate confidence
            if self.ml_model.is_available():
                logger.warning("ML model available but could not generate signal, using rules only")

        analysis["ensemble_signal"] = ensemble_signal
        analysis["ensemble_confidence"] = ensemble_confidence

        return ensemble_signal, analysis

    def get_model_status(self) -> Dict:
        """Get status of the ensemble and models"""
        return {
            "ensemble_ready": True,
            "ml_model_available": self.ml_model.is_available(),
            "ml_model_loaded": self.ml_model.model_loaded,
            "rule_weight": self.rule_weight,
            "ml_weight": self.ml_weight
        }
