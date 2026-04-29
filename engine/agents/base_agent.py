import asyncio
import logging
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentMessage:
    sender: str
    topic: str
    payload: Any


class BaseAgent:
    """
    Lightweight async agent.  Each agent shares a single asyncio.Queue (bus)
    so any agent can publish events that the orchestrator or other agents
    can observe.
    """

    name: str = "base"

    def __init__(self, bus: asyncio.Queue):
        self.bus = bus
        self.logger = logging.getLogger(f"agent.{self.name}")

    async def publish(self, topic: str, payload: Any):
        await self.bus.put(AgentMessage(sender=self.name, topic=topic, payload=payload))
        self.logger.debug(f"[{topic}] published")

    async def run(self, **kwargs):
        raise NotImplementedError
