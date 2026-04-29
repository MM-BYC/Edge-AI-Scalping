#!/usr/bin/env python3
"""
Edge AI Scalping Bot - Main orchestrator
Runs on Mac mini, orchestrates all trading logic and iOS communication
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

import uvicorn
import uvloop

# High-performance event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from engine.agents.live_feedback_agent import LiveFeedbackAgent
from engine.agents.orchestrator import RetrainingOrchestrator
from engine.api.server import create_app, set_bot_running, set_dependencies
from engine.broker.alpaca_client import AlpacaClient
from engine.config import settings
from engine.data.feed import DataFeed
from engine.execution.credit_spread_router import CreditSpreadRouter
from engine.execution.options_router import ZeroDTERouter
from engine.execution.options_tracker import OptionsTracker
from engine.execution.pnl_tracker import PnLTracker
from engine.execution.risk import RiskManager
from engine.execution.router import OrderRouter
from engine.execution.sell_put_router import SellPutRouter
from engine.scheduler import NightlyScheduler
from engine.signals.ensemble import SignalEnsemble

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.FileHandler(settings.log_file)  # Uncomment to enable file logging
    ],
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self):
        logger.info("Initializing Edge AI Scalping Bot")
        logger.info(f"Mode: {settings.mode.upper()}")
        logger.info(f"Symbols: {settings.symbols_list}")

        # Core components
        self.alpaca = AlpacaClient()
        self.feed = DataFeed(self.alpaca)
        self.ensemble = SignalEnsemble(str(settings.model_path_full))
        self.risk = RiskManager()
        self.pnl = PnLTracker()
        self.router = OrderRouter(self.alpaca, self.risk, self.pnl)
        self.options = OptionsTracker()

        # 0DTE SPY credit spread router (opt-in via ZERO_DTE_ENABLED=true in .env)
        self._zero_dte: Optional[ZeroDTERouter] = (
            ZeroDTERouter(self.alpaca, self.options, self.risk)
            if settings.zero_dte_enabled
            else None
        )
        if self._zero_dte:
            logger.info("0DTE SPY credit spread mode enabled")

        # Sell Put and Credit Spread routers (always on; symbols configured via iOS)
        self._sell_put = SellPutRouter(self.alpaca, self.options, self.risk)
        self._credit_spread = CreditSpreadRouter(self.alpaca, self.options, self.risk)
        if settings.is_paper and settings.paper_options_sim:
            logger.info("Options paper simulation mode enabled (sell-put, credit-spread, 0DTE)")

        # State
        self.is_running = False
        self.last_bar_time = {}

        # Nightly retraining pipeline
        self._orchestrator = RetrainingOrchestrator(ensemble=self.ensemble)
        self._scheduler = NightlyScheduler(self._orchestrator)

        # Intraday live feedback (adjusts ensemble weights from live trade outcomes)
        self._live_feedback = LiveFeedbackAgent(
            bus=self._orchestrator.bus,
            registry=self._orchestrator.registry,
            pnl_tracker=self.pnl,
            ensemble=self.ensemble,
        )

        # Register callbacks
        self.feed.add_callback(self._on_new_bar)

    async def start(self):
        """Start the bot"""
        logger.info("Bot starting...")

        try:
            # Connect to broker
            await self.feed.start()
            logger.info("Data feed connected")

            # Start API server
            self._start_api_server()

            # Set dependencies for API
            set_dependencies(
                self.pnl, self.risk, self.options, self.feed,
                sp_router=self._sell_put,
                cs_router=self._credit_spread,
            )

            self.is_running = True
            set_bot_running(True)
            await self._sync_alpaca_account()
            await self._sync_alpaca_positions_once()
            logger.info("Bot ready, waiting for market data...")

            # Start nightly retraining scheduler in background
            asyncio.create_task(self._scheduler.start())
            logger.info("Nightly retraining scheduler started")

            # Start intraday feedback agent in background
            asyncio.create_task(self._live_feedback.start())
            logger.info("LiveFeedbackAgent started")

            # Sync open positions from Alpaca every 15s so iOS always shows reality
            asyncio.create_task(self._sync_alpaca_positions())
            logger.info("Position sync started (15s interval)")

        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

    async def stop(self):
        """Stop the bot"""
        logger.info("Bot stopping...")

        try:
            # Close all positions
            await self.router.close_all_positions("shutdown")

            # Stop background agents
            self._scheduler.stop()
            self._live_feedback.stop()

            # Close options positions and clean up
            if self._zero_dte:
                await self._zero_dte.close_all()
                await self._zero_dte.aclose()
            await self._sell_put.close_all()
            await self._sell_put.aclose()
            await self._credit_spread.close_all()
            await self._credit_spread.aclose()

            # Disconnect
            await self.feed.stop()

            self.is_running = False
            set_bot_running(False)
            logger.info("Bot stopped")

        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

    def _start_api_server(self):
        """Start FastAPI server in background task"""
        app = create_app()
        config = uvicorn.Config(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.api_log_level,
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Run server in background
        def run_server():
            asyncio.run(server.serve())

        import threading

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info(f"API server started on {settings.api_host}:{settings.api_port}")

    def _on_new_bar(self, bar):
        """Called when a new bar arrives"""
        if not self.is_running:
            return

        symbol = bar.symbol

        # Throttle to avoid duplicate signals (max 1 signal per second per symbol)
        last_time = self.last_bar_time.get(symbol, 0)
        if time.time() - last_time < 0.5:
            return

        self.last_bar_time[symbol] = time.time()

        # Get buffer
        buffer = self.feed.get_buffer(symbol)
        if not buffer or not buffer.is_ready(20):
            return

        # Get OHLCV arrays
        timestamps, opens, highs, lows, closes, volumes = buffer.get_numpy_arrays(100)

        if len(closes) == 0:
            return

        # Generate signal
        signal, analysis = self.ensemble.generate_signal(opens, highs, lows, closes, volumes)

        confidence = analysis.get("ensemble_confidence", 0.5)

        # Log signal
        if signal != 0:
            logger.info(
                f"Signal: {symbol} -> {signal:+d} (confidence={confidence:.2%}) "
                f"[rules={analysis.get('rule_signal')}, ml={analysis.get('ml_signal')}, "
                f"price=${bar.close:.2f}]"
            )

        # Update P&L
        self.pnl.update_market_prices(symbol, bar.close)

        # Route equity signal
        asyncio.create_task(self.router.route_signal(symbol, signal, bar.close, confidence))

        # Route options signals (each router filters by its own symbol list)
        asyncio.create_task(self._sell_put.route_signal(symbol, signal, bar.close, confidence))
        asyncio.create_task(self._credit_spread.route_signal(symbol, signal, bar.close, confidence))

        # Route 0DTE signal for SPY when enabled
        if self._zero_dte and symbol == "SPY":
            asyncio.create_task(self._zero_dte.route_signal(signal, bar.close, confidence))

    async def run(self):
        """Main event loop"""
        logger.info("Starting main trading loop...")

        try:
            # Keep running
            while self.is_running:
                # Periodic status update
                await asyncio.sleep(5)

                stats = self.pnl.get_stats()
                risk_status = self.risk.get_status()

                logger.debug(
                    f"Status: equity=${self.risk.metrics.total_equity:.2f}, "
                    f"pnl=${stats['total_pnl']:.2f}, positions={stats['open_positions']}, "
                    f"trades={stats['total_trades']}, can_trade={risk_status['can_trade']}"
                )

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            await self.stop()

    async def _sync_alpaca_positions(self):
        """Pull account and open positions from Alpaca every 15s."""
        while self.is_running:
            try:
                await self._sync_alpaca_account()
                await self._sync_alpaca_positions_once()
            except Exception as e:
                logger.warning(f"Position sync error: {e}")
            await asyncio.sleep(15)

    async def _sync_alpaca_account(self):
        """Seed risk metrics from Alpaca account values used by iOS dashboard."""
        account = await self.alpaca.get_account()
        if isinstance(account, dict):
            self.risk.update_metrics(account)

    async def _sync_alpaca_positions_once(self):
        """Seed PnL tracker from currently open broker positions."""
        positions = await self.alpaca.get_positions()
        if isinstance(positions, list):
            self.pnl.sync_from_broker(positions)
            self.risk.metrics.position_count = len(positions)

    def handle_shutdown(self, signum, frame):
        """Handle SIGTERM/SIGINT"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False


async def main():
    """Main entry point"""
    bot = TradingBot()

    # Handle shutdown signals
    def shutdown_handler(signum, frame):
        bot.handle_shutdown(signum, frame)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        await bot.start()
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Verify .env is configured
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        sys.exit(1)

    logger.info(f"Python {sys.version}")
    logger.info(f"Project root: {settings.project_root}")

    asyncio.run(main())
