from datetime import datetime

from engine.execution.risk import RiskManager


def test_trade_loss_sets_future_cooldown_after_loss_streak(monkeypatch):
    risk = RiskManager()
    monkeypatch.setattr(risk.config, "cooldown_trades", 1)
    monkeypatch.setattr(risk.config, "cooldown_minutes", 15)

    risk.on_trade_loss()

    assert risk.cooldown_until is not None
    assert risk.cooldown_until > datetime.now()
