"""Verifies the core reliability claim of the outbox pattern:

command commit -> outbox row appears -> projector processes it -> Mongo
document reflects the change — and that this still holds if the projector
was "down" (not run) when the command happened, i.e. it catches up.

Requires Docker (testcontainers spins up real Postgres + Mongo).
"""

import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.mongodb import MongoDbContainer
from testcontainers.postgres import PostgresContainer

from app.command.handlers import CreateProjectCommand, CreateTaskCommand, create_project, create_task
from app.command.models import Base
from app.outbox import projector as projector_module
from app.outbox.models import OutboxEvent  # noqa: F401
from app.outbox.projector import run_once


@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def mongo_container():
    with MongoDbContainer("mongo:7") as mongo:
        yield mongo


@pytest.fixture
async def session_factory(postgres_container):
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def mongo_collections(mongo_container, monkeypatch):
    client = AsyncIOMotorClient(mongo_container.get_connection_url())
    db = client["taskflow_test"]
    monkeypatch.setattr(projector_module, "project_boards", db["project_boards"])
    monkeypatch.setattr(projector_module, "user_workload", db["user_workload"])
    yield db
    client.close()


async def test_command_to_outbox_to_projector_to_mongo(session_factory, mongo_collections):
    async with session_factory() as session:
        project = await create_project(
            session, CreateProjectCommand(name="Redesign Website", owner_id=uuid.uuid4())
        )
        task = await create_task(
            session, CreateTaskCommand(project_id=project.id, title="Design homepage")
        )

    # Simulate the projector having been "down": events sit as PENDING until
    # we explicitly run it now.
    async with session_factory() as session:
        pending = (
            await session.execute(
                OutboxEvent.__table__.select().where(OutboxEvent.status == "PENDING")
            )
        ).fetchall()
        assert len(pending) == 2  # ProjectCreated + TaskCreated

    async with session_factory() as session:
        processed_count = await run_once(session)
        assert processed_count == 2

    board = await mongo_collections["project_boards"].find_one({"_id": str(project.id)})
    assert board is not None
    assert board["project_name"] == "Redesign Website"
    assert any(t["task_id"] == str(task.id) for t in board["columns"]["TODO"])

    async with session_factory() as session:
        remaining_pending = (
            await session.execute(
                OutboxEvent.__table__.select().where(OutboxEvent.status == "PENDING")
            )
        ).fetchall()
        assert len(remaining_pending) == 0


async def test_projector_idempotent_on_reprocessing(session_factory, mongo_collections):
    """Re-running process_event for an already-processed event must not corrupt
    the read model — the board rebuild is a full recompute, not an increment."""
    async with session_factory() as session:
        project = await create_project(
            session, CreateProjectCommand(name="P2", owner_id=uuid.uuid4())
        )
        await create_task(session, CreateTaskCommand(project_id=project.id, title="Task A"))

    async with session_factory() as session:
        await run_once(session)

    async with session_factory() as session:
        event = (
            await session.execute(
                OutboxEvent.__table__.select().where(OutboxEvent.aggregate_id == project.id)
            )
        ).first()
        await projector_module.process_event(session, OutboxEvent(**event._mapping))

    board = await mongo_collections["project_boards"].find_one({"_id": str(project.id)})
    assert len(board["columns"]["TODO"]) == 1
