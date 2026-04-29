from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    # Alpaca API
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # Trading
    mode: str = "paper"  # paper | live
    symbols: str = "SPY,QQQ"

    # Risk management
    daily_loss_cap: float = -0.02
    max_concurrent_positions: int = 5
    per_trade_stop_loss: float = -0.003
    options_max_delta: float = 0.5
    cooldown_trades: int = 3
    cooldown_minutes: int = 15

    # ML model
    ml_model_path: str = "engine/models/scalp_v1.onnx"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8765
    api_log_level: str = "info"

    # Backtesting
    backtest_lookback_days: int = 365
    backtest_train_days: int = 60
    backtest_test_days: int = 10

    # Nightly retraining
    retrain_lookback_days: int = 90       # days of history to fetch per run
    retrain_min_improvement: float = 0.01 # min win-rate delta to deploy a new model

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/engine.log"

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-detect live vs paper based on API URL
        if "live" in self.mode.lower():
            self.alpaca_base_url = "https://api.alpaca.markets"
            self.alpaca_data_url = "https://data.alpaca.markets"
        else:
            self.alpaca_base_url = "https://paper-api.alpaca.markets"
            self.alpaca_data_url = "https://data.alpaca.markets"

    @property
    def is_paper(self) -> bool:
        return self.mode.lower() == "paper"

    @property
    def is_live(self) -> bool:
        return self.mode.lower() == "live"

    @property
    def symbols_list(self) -> List[str]:
        return [s.strip() for s in self.symbols.split(",")]

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def model_path_full(self) -> Path:
        path = Path(self.ml_model_path)
        if not path.is_absolute():
            path = self.project_root / path
        return path


settings = Settings()
