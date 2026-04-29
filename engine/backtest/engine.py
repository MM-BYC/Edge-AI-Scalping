#!/usr/bin/env python3
"""
Backtesting engine for strategy validation
Replays signal ensemble on historical data
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class BacktestBar:
    """Historical bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class BacktestTrade:
    """Backtested trade record"""
    symbol: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    qty: int
    side: str
    pnl: float
    pnl_pct: float
    bars_held: int


@dataclass
class BacktestMetrics:
    """Backtest performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    gross_pnl: float = 0.0
    commissions: float = 0.0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_hold_bars: float = 0.0
    starting_equity: float = 100000.0
    ending_equity: float = 100000.0
    total_return: float = 0.0


class BacktestEngine:
    """Replay trading signals on historical data"""

    def __init__(self, signal_generator, starting_equity: float = 100000.0, commission_pct: float = 0.001):
        self.signal_generator = signal_generator
        self.starting_equity = starting_equity
        self.commission_pct = commission_pct

        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = []
        self.metrics = BacktestMetrics(starting_equity=starting_equity, ending_equity=starting_equity)

    def run(self, symbol: str, bars: List[BacktestBar], position_size_pct: float = 0.02) -> BacktestMetrics:
        """
        Run backtest on historical bars
        Returns: BacktestMetrics
        """
        logger.info(f"Running backtest on {symbol} with {len(bars)} bars")

        if len(bars) < 20:
            logger.error("Not enough bars for backtest")
            return self.metrics

        current_equity = self.starting_equity
        open_position = None
        equity_values = [current_equity]
        open_trades = []

        # Convert bars to arrays for signal generation
        opens = np.array([b.open for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])

        # Walk through each bar
        for i in range(20, len(bars)):  # Start from bar 20 (need 20 for indicators)
            bar = bars[i]
            current_close = bar.close

            # Get OHLCV up to this point
            opens_slice = opens[:i+1]
            highs_slice = highs[:i+1]
            lows_slice = lows[:i+1]
            closes_slice = closes[:i+1]
            volumes_slice = volumes[:i+1]

            # Generate signal
            signal, analysis = self.signal_generator.generate_signal(
                opens_slice, highs_slice, lows_slice, closes_slice, volumes_slice
            )

            # Check open position P&L
            if open_position is not None:
                pnl = (current_close - open_position["entry_price"]) * open_position["qty"]
                pnl_pct = (current_close - open_position["entry_price"]) / open_position["entry_price"]

                # Stop loss at -0.3%
                if pnl_pct <= -0.003:
                    # Close position
                    commission = abs(open_position["qty"] * current_close * self.commission_pct)
                    net_pnl = pnl - commission
                    current_equity += net_pnl

                    trade = BacktestTrade(
                        symbol=symbol,
                        entry_time=bars[open_position["entry_bar"]].timestamp,
                        entry_price=open_position["entry_price"],
                        exit_time=bar.timestamp,
                        exit_price=current_close,
                        qty=open_position["qty"],
                        side="long",
                        pnl=net_pnl,
                        pnl_pct=pnl_pct,
                        bars_held=i - open_position["entry_bar"]
                    )
                    self.trades.append(trade)
                    open_position = None

                    self.metrics.losing_trades += 1

            # Generate entry signal
            if signal == 1 and open_position is None:
                # Calculate position size
                position_value = current_equity * position_size_pct
                qty = max(1, int(position_value / current_close))

                # Enter position
                commission = qty * current_close * self.commission_pct
                current_equity -= commission

                open_position = {
                    "entry_price": current_close,
                    "entry_bar": i,
                    "qty": qty
                }

            # Take profit at +0.5%
            elif signal == -1 and open_position is not None:
                pnl = (current_close - open_position["entry_price"]) * open_position["qty"]
                pnl_pct = (current_close - open_position["entry_price"]) / open_position["entry_price"]

                if pnl_pct >= 0.005:
                    # Close position
                    commission = abs(open_position["qty"] * current_close * self.commission_pct)
                    net_pnl = pnl - commission
                    current_equity += net_pnl

                    trade = BacktestTrade(
                        symbol=symbol,
                        entry_time=bars[open_position["entry_bar"]].timestamp,
                        entry_price=open_position["entry_price"],
                        exit_time=bar.timestamp,
                        exit_price=current_close,
                        qty=open_position["qty"],
                        side="long",
                        pnl=net_pnl,
                        pnl_pct=pnl_pct,
                        bars_held=i - open_position["entry_bar"]
                    )
                    self.trades.append(trade)
                    open_position = None

                    self.metrics.winning_trades += 1

            equity_values.append(current_equity)

        # Close any remaining position at last bar
        if open_position is not None:
            bar = bars[-1]
            pnl = (bar.close - open_position["entry_price"]) * open_position["qty"]
            pnl_pct = (bar.close - open_position["entry_price"]) / open_position["entry_price"]
            commission = abs(open_position["qty"] * bar.close * self.commission_pct)
            net_pnl = pnl - commission
            current_equity += net_pnl

            trade = BacktestTrade(
                symbol=symbol,
                entry_time=bars[open_position["entry_bar"]].timestamp,
                entry_price=open_position["entry_price"],
                exit_time=bar.timestamp,
                exit_price=bar.close,
                qty=open_position["qty"],
                side="long",
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                bars_held=len(bars) - 1 - open_position["entry_bar"]
            )
            self.trades.append(trade)

            if pnl_pct > 0:
                self.metrics.winning_trades += 1
            else:
                self.metrics.losing_trades += 1

        # Calculate metrics
        self.equity_curve = equity_values
        self._calculate_metrics(current_equity)

        return self.metrics

    def _calculate_metrics(self, final_equity: float):
        """Calculate performance metrics"""
        self.metrics.ending_equity = final_equity
        self.metrics.total_return = (final_equity - self.starting_equity) / self.starting_equity
        self.metrics.total_trades = len(self.trades)

        if self.metrics.total_trades == 0:
            logger.warning("No trades generated")
            return

        # Win rate
        self.metrics.win_rate = (
            self.metrics.winning_trades / self.metrics.total_trades
            if self.metrics.total_trades > 0 else 0
        )

        # P&L stats
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl < 0]

        self.metrics.gross_pnl = sum(t.pnl for t in self.trades)
        self.metrics.commissions = self.metrics.starting_equity - self.starting_equity + self.metrics.gross_pnl - self.metrics.ending_equity
        self.metrics.net_pnl = self.metrics.gross_pnl - self.metrics.commissions

        self.metrics.avg_win = sum(wins) / len(wins) if wins else 0
        self.metrics.avg_loss = sum(losses) / len(losses) if losses else 0

        if abs(self.metrics.avg_loss) > 0:
            self.metrics.profit_factor = abs(sum(wins) / sum(losses)) if losses else 0
        else:
            self.metrics.profit_factor = 0

        # Hold time
        hold_times = [t.bars_held for t in self.trades]
        self.metrics.avg_hold_bars = sum(hold_times) / len(hold_times) if hold_times else 0

        # Drawdown
        equity_array = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - running_max) / running_max
        self.metrics.max_drawdown = float(np.min(drawdowns))

        # Sharpe (approximate, using daily returns)
        returns = np.diff(equity_array) / equity_array[:-1]
        if len(returns) > 0 and np.std(returns) > 0:
            self.metrics.sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
        else:
            self.metrics.sharpe_ratio = 0

        logger.info(f"Backtest complete: {self.metrics}")

    def __repr__(self) -> str:
        return (
            f"Backtest(trades={self.metrics.total_trades}, "
            f"win_rate={self.metrics.win_rate:.1%}, "
            f"pnl=${self.metrics.net_pnl:.2f}, "
            f"sharpe={self.metrics.sharpe_ratio:.2f})"
        )
