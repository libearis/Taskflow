import asyncio
import contextlib
import logging

import grpc
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import boards, health, projects, tasks
from app.config import settings
from app.grpc_server.generated import board_stream_pb2_grpc, issue_intake_pb2_grpc
from app.grpc_server.issue_intake_servicer import IssueIntakeServicer
from app.grpc_server.servicer import BoardStreamServicer
from app.outbox.projector import run_forever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="TaskFlow API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(boards.router)
    return app


app = create_app()


async def serve_grpc(stop_event: asyncio.Event) -> None:
    server = grpc.aio.server()
    # Two services, one server, one port — IssueIntake (external issue
    # reports, e.g. from the .NET Catalog & Order Performance Lab) rides on
    # the same gRPC server as BoardStreamService rather than a second one,
    # since a second server can't bind the same port anyway.
    board_stream_pb2_grpc.add_BoardStreamServiceServicer_to_server(BoardStreamServicer(), server)
    issue_intake_pb2_grpc.add_IssueIntakeServicer_to_server(IssueIntakeServicer(), server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    await server.start()
    logger.info(
        "gRPC server (StreamBoardUpdates, IssueIntake) listening on :%s", settings.grpc_port
    )
    await stop_event.wait()
    await server.stop(grace=5)


async def serve_http() -> None:
    config = uvicorn.Config(app, host="0.0.0.0", port=settings.http_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    stop_event = asyncio.Event()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(serve_http())
        tg.create_task(serve_grpc(stop_event))
        tg.create_task(run_forever())


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
