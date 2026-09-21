from typing import AsyncIterator

import grpc

from app.grpc_server.generated import board_stream_pb2, board_stream_pb2_grpc
from app.grpc_server.pubsub import board_event_bus


class BoardStreamServicer(board_stream_pb2_grpc.BoardStreamServiceServicer):
    """Implements StreamBoardUpdates only — the single RPC this project uses gRPC for."""

    async def StreamBoardUpdates(
        self,
        request: board_stream_pb2.StreamBoardRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncIterator[board_stream_pb2.BoardUpdateEvent]:
        async for event in board_event_bus.stream(request.project_id):
            yield board_stream_pb2.BoardUpdateEvent(
                task_id=event["task_id"],
                title=event.get("title", ""),
                old_status=event.get("old_status", ""),
                new_status=event.get("new_status", ""),
                assignee_id=event.get("assignee_id") or "",
                changed_at=event["changed_at"],
            )
