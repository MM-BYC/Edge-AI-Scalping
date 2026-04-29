#!/usr/bin/env python3
"""
Train ML model for scalping signals
Generates OHLCV features and trains LightGBM classifier
"""

import logging
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    import pandas as pd
    TRAIN_AVAILABLE = True
except ImportError:
    TRAIN_AVAILABLE = False
    logger.warning("LightGBM not available, training disabled")


def generate_features(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                     closes: np.ndarray, volumes: np.ndarray, lookback: int = 20) -> np.ndarray:
    """
    Generate 20 features from OHLCV data
    Features: normalized prices, returns, volatility, volume ratio
    """
    features = []

    if len(closes) < lookback:
        return None

    # Get slice
    closes_slice = closes[-lookback:].astype(np.float64)
    opens_slice = opens[-lookback:].astype(np.float64)
    highs_slice = highs[-lookback:].astype(np.float64)
    lows_slice = lows[-lookback:].astype(np.float64)
    volumes_slice = volumes[-lookback:].astype(np.float64)

    # Close prices (normalized)
    close_mean = np.mean(closes_slice)
    close_std = np.std(closes_slice) + 1e-8
    normalized_closes = (closes_slice - close_mean) / close_std
    features.extend(normalized_closes[:10].tolist())

    # Returns
    returns = np.diff(np.log(closes_slice + 1e-8))
    features.extend(returns[:9].tolist())

    # High-Low range (volatility proxy)
    hl_range = (highs_slice - lows_slice) / closes_slice
    features.append(np.mean(hl_range))

    # Pad to exactly 20
    while len(features) < 20:
        features.append(0.0)
    features = features[:20]

    return np.array(features, dtype=np.float32)


def generate_targets(closes: np.ndarray, threshold: float = 0.003) -> np.ndarray:
    """
    Generate classification targets
    1: next bar closes up >= threshold
    -1: next bar closes down <= -threshold
    0: flat
    """
    targets = []
    for i in range(len(closes) - 1):
        current = closes[i]
        next_close = closes[i + 1]
        pct_change = (next_close - current) / current

        if pct_change >= threshold:
            targets.append(2)  # Maps to 1 in ONNX output
        elif pct_change <= -threshold:
            targets.append(0)  # Maps to -1 in ONNX output
        else:
            targets.append(1)  # Maps to 0 (hold) in ONNX output

    return np.array(targets, dtype=np.int32)


class DummyModel:
    """Placeholder model that returns random signals (used when LightGBM not available)"""

    def __init__(self):
        self.feature_names = [f"f_{i}" for i in range(20)]

    def predict(self, X):
        """Return random predictions"""
        return np.random.randint(0, 3, size=len(X))


def train_model(X_train: np.ndarray, y_train: np.ndarray,
                X_val: np.ndarray, y_val: np.ndarray) -> object:
    """
    Train LightGBM model
    Returns: trained model
    """
    if not TRAIN_AVAILABLE:
        logger.warning("LightGBM not available, returning dummy model")
        return DummyModel()

    logger.info(f"Training LightGBM on {len(X_train)} samples")

    # Create dataset
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    # Parameters
    params = {
        'objective': 'multiclass',
        'num_class': 3,
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'max_depth': 5,
        'verbose': 0
    }

    # Train
    model = lgb.train(
        params,
        train_data,
        num_boost_round=100,
        valid_sets=[train_data, val_data],
        valid_names=['train', 'val'],
        callbacks=[lgb.log_evaluation(period=20)]
    )

    logger.info(f"Model trained successfully")
    return model


def export_onnx(model: object, output_path: str):
    """
    Export LightGBM model to ONNX format
    """
    try:
        import onnxmltools
        from skl2onnx.common.data_types import FloatTensorType

        # Convert to ONNX
        initial_type = [('float_input', FloatTensorType([None, 20]))]
        onnx_model = onnxmltools.convert_lightgbm(model, initial_types=initial_type)

        # Save
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        onnxmltools.utils.save_model(onnx_model, output_path)

        logger.info(f"Model exported to {output_path}")
        return True

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        return False


def create_dummy_model_onnx(output_path: str):
    """Create a minimal ONNX model for testing (when LightGBM not available)"""
    try:
        import onnx
        import onnx.helper as helper

        # Create a simple identity-like model that outputs class probabilities
        X = helper.make_tensor_value_info('float_input', onnx.TensorProto.FLOAT, [None, 20])
        Y = helper.make_tensor_value_info('probabilities', onnx.TensorProto.FLOAT, [None, 3])

        # Create constant output (dummy)
        const_tensor = helper.make_tensor(
            name='const',
            data_type=onnx.TensorProto.FLOAT,
            dims=[1, 3],
            vals=[0.33, 0.33, 0.34]
        )

        # Dummy node
        node = helper.make_node(
            'Identity',
            inputs=['float_input'],
            outputs=['output'],
            name='identity'
        )

        graph = helper.make_graph(
            [node],
            'scalp_model',
            [X],
            [helper.make_tensor_value_info('output', onnx.TensorProto.FLOAT, [None, 20])]
        )

        model = helper.make_model(graph, producer_name='EdgeAI')
        onnx.checker.check_model(model)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        onnx.save(model, output_path)

        logger.info(f"Dummy ONNX model created at {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create dummy ONNX model: {e}")
        return False


def simulate_training_data(num_samples: int = 1000):
    """
    Simulate training data (for demo)
    In production, download from Alpaca API
    """
    logger.info(f"Generating {num_samples} simulated samples")

    X = np.random.randn(num_samples, 20).astype(np.float32)
    y = np.random.randint(0, 3, size=num_samples)

    return X, y


def main():
    """Train and export model"""
    import sys
    from engine.config import settings

    logging.basicConfig(level=logging.INFO)

    logger.info("=== Edge AI Model Training ===")
    logger.info(f"Model output: {settings.model_path_full}")

    # Generate or load data
    X, y = simulate_training_data(num_samples=1000)

    # Split: 80% train, 20% validation
    split_idx = int(0.8 * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # Train
    model = train_model(X_train, y_train, X_val, y_val)

    # Export ONNX
    if TRAIN_AVAILABLE:
        success = export_onnx(model, str(settings.model_path_full))
    else:
        success = create_dummy_model_onnx(str(settings.model_path_full))

    if success:
        logger.info("Training complete!")
        return 0
    else:
        logger.error("Training failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
