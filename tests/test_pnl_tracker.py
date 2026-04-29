from engine.execution.pnl_tracker import PnLTracker


def test_record_fill_opens_position():
    t = PnLTracker()
    t.record_fill("AAPL", "buy", 10, 150.0)
    trades = t.get_open_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "AAPL"
    assert trades[0]["qty"] == 10
    assert trades[0]["entry_price"] == 150.0


def test_record_fill_closes_position():
    t = PnLTracker()
    t.record_fill("AAPL", "buy", 10, 150.0)
    t.record_fill("AAPL", "sell", 10, 155.0)
    assert len(t.get_open_trades()) == 0
    stats = t.get_stats()
    assert stats["realized_pnl"] == 50.0
    assert stats["winning_trades"] == 1


def test_update_market_prices():
    t = PnLTracker()
    t.record_fill("SPY", "buy", 5, 500.0)
    t.update_market_prices("SPY", 502.0)
    trades = t.get_open_trades()
    assert trades[0]["current_price"] == 502.0
    assert trades[0]["unrealized_pnl"] == 10.0


def test_sync_from_broker_adds_missed_fill():
    t = PnLTracker()
    broker_positions = [
        {
            "symbol": "QQQ",
            "qty": "3",
            "avg_entry_price": "440.0",
            "current_price": "442.0",
            "unrealized_pl": "6.0",
            "unrealized_plpc": "0.00454",
        }
    ]
    t.sync_from_broker(broker_positions)
    trades = t.get_open_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "QQQ"
    assert trades[0]["entry_price"] == 440.0


def test_sync_from_broker_removes_closed_position():
    t = PnLTracker()
    t.record_fill("TSLA", "buy", 2, 200.0)
    assert len(t.get_open_trades()) == 1
    # Broker reports no positions — TSLA was closed externally
    t.sync_from_broker([])
    assert len(t.get_open_trades()) == 0


def test_win_rate():
    t = PnLTracker()
    t.record_fill("A", "buy", 1, 100.0)
    t.record_fill("A", "sell", 1, 110.0)  # win
    t.record_fill("B", "buy", 1, 100.0)
    t.record_fill("B", "sell", 1, 90.0)   # loss
    stats = t.get_stats()
    assert stats["win_rate_pct"] == 50.0
