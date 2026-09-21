"""In-process pub/sub for BoardStreamService.

No message broker: the projector pushes into this bus right after it
finishes writing to Mongo, and each active StreamBoardUpdates RPC owns a
per-connection asyncio.Queue subscribed to its project_id.
"""

import asyncio
from collections import defaultdict
from typing import AsyncIterator


class BoardEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, project_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[project_id].add(queue)
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[project_id].discard(queue)
        if not self._subscribers[project_id]:
            del self._subscribers[project_id]

    async def publish(self, project_id: str, event: dict) -> None:
        for queue in list(self._subscribers.get(project_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer drops events rather than blocking the projector

    async def stream(self, project_id: str) -> AsyncIterator[dict]:
        queue = self.subscribe(project_id)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(project_id, queue)


board_event_bus = BoardEventBus()
