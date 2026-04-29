import asyncio
import logging
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
# Fire 15 minutes after regular market close (16:00 ET → 16:15 ET)
_TRIGGER_HOUR   = 16
_TRIGGER_MINUTE = 15


class NightlyScheduler:
    """
    Wakes up once per weekday at 16:15 ET and triggers the retraining
    pipeline.  Runs as a background asyncio task alongside the trading bot.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self._running = False

    async def start(self):
        self._running = True
        logger.info("NightlyScheduler started")
        while self._running:
            wait = self._seconds_until_trigger()
            fire_at = datetime.now(_ET) + timedelta(seconds=wait)
            logger.info(f"Next retraining run scheduled for {fire_at.strftime('%Y-%m-%d %H:%M %Z')}")
            await asyncio.sleep(wait)

            if not self._running:
                break

            now = datetime.now(_ET)
            if now.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
                logger.info("Weekend — skipping retraining")
                continue

            logger.info("Triggering nightly retraining pipeline")
            try:
                await self.orchestrator.run()
            except Exception as exc:
                logger.error(f"Retraining pipeline error: {exc}", exc_info=True)

    def stop(self):
        self._running = False
        logger.info("NightlyScheduler stopped")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _seconds_until_trigger(self) -> float:
        now    = datetime.now(_ET)
        target = now.replace(
            hour=_TRIGGER_HOUR,
            minute=_TRIGGER_MINUTE,
            second=0,
            microsecond=0,
        )
        if now >= target:
            # Already past today's window — aim for next calendar day
            # (the weekday check above will skip weekends)
            target += timedelta(days=1)

        return max(1.0, (target - now).total_seconds())
