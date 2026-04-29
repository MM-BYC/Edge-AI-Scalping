from engine.execution.options_tracker import OptionsTracker


def test_open_sell_put():
    t = OptionsTracker()
    t.open_position("sell_put", "TSLY", 20.0, "2026-04-29", premium=0.50, qty=1)
    positions = t.get_sell_put_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "TSLY"
    assert positions[0]["premium_collected"] == 0.50


def test_unrealized_pnl_positive_when_value_decays():
    t = OptionsTracker()
    t.open_position("sell_put", "NVDY", 15.0, "2026-04-29", premium=1.00, qty=1)
    t.update_mark("sell_put", "NVDY", 15.0, "2026-04-29", current_value=0.50)
    positions = t.get_sell_put_positions()
    assert positions[0]["unrealized_pnl"] == 50.0   # (1.00 - 0.50) * 1 * 100


def test_close_records_realized_pnl():
    t = OptionsTracker()
    t.open_position("credit_spread", "SPY", 500.0, "2026-04-29", premium=0.80, qty=2)
    t.close_position("credit_spread", "SPY", 500.0, "2026-04-29", close_value=0.30)
    stats = t.get_credit_spread_stats()
    assert stats["realized_pnl"] == pytest.approx(100.0)   # (0.80-0.30)*2*100
    assert stats["open_positions"] == 0
    assert stats["win_rate"] == 1.0


def test_zero_dte_bucket_separate_from_credit_spread():
    t = OptionsTracker()
    t.open_position("0dte", "SPY", 498.0, "2026-04-29", premium=0.40, qty=1)
    assert len(t.get_zero_dte_positions()) == 1
    assert len(t.get_credit_spread_positions()) == 0


def test_winning_symbol_returns_best():
    t = OptionsTracker()
    t.open_position("sell_put", "TSLY", 20.0, "2026-04-29", premium=1.00, qty=1)
    t.open_position("sell_put", "NVDY", 15.0, "2026-04-29", premium=0.50, qty=1)
    t.update_mark("sell_put", "TSLY", 20.0, "2026-04-29", current_value=0.20)   # big winner
    t.update_mark("sell_put", "NVDY", 15.0, "2026-04-29", current_value=0.45)   # small winner
    assert t.get_winning_sell_put() == "TSLY"


import pytest
