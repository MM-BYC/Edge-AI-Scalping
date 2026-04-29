#!/usr/bin/env python3
"""Root entrypoint for running the bot with `python main.py`."""

import asyncio
import sys

from engine.config import settings
from engine.main import logger, main


if __name__ == "__main__":
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        sys.exit(1)

    logger.info(f"Python {sys.version}")
    logger.info(f"Project root: {settings.project_root}")

    asyncio.run(main())
