import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.command.handlers import (
    ChangeTaskStatusCommand,
    CreateProjectCommand,
    CreateTaskCommand,
    InvalidStatusError,
    TaskNotFoundError,
    change_task_status,
    create_project,
    create_task,
)
from app.command.models import Base
from app.outbox.models import OutboxEvent  # noqa: F401 — registers table with Base.metadata


@pytest.fixture
async def session():
    # SQLite in-memory stands in for Postgres in unit tests: fast, no network,
    # good enough to verify handler + outbox-write logic in one transaction.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


async def test_create_project_writes_outbox_event(session):
    project = await create_project(
        session, CreateProjectCommand(name="Redesign Website", owner_id=uuid.uuid4())
    )

    events = (await session.execute(OutboxEvent.__table__.select())).fetchall()
    assert len(events) == 1
    assert events[0].event_type == "ProjectCreated"
    assert events[0].aggregate_id == project.id


async def test_create_task_writes_outbox_event(session):
    project = await create_project(session, CreateProjectCommand(name="P", owner_id=uuid.uuid4()))
    task = await create_task(session, CreateTaskCommand(project_id=project.id, title="Do the thing"))

    assert task.status == "TODO"
    events = (
        await session.execute(
            OutboxEvent.__table__.select().where(OutboxEvent.event_type == "TaskCreated")
        )
    ).fetchall()
    assert len(events) == 1


async def test_change_task_status_writes_transition_event(session):
    project = await create_project(session, CreateProjectCommand(name="P", owner_id=uuid.uuid4()))
    task = await create_task(session, CreateTaskCommand(project_id=project.id, title="T"))

    updated = await change_task_status(
        session, ChangeTaskStatusCommand(task_id=task.id, new_status="IN_PROGRESS")
    )

    assert updated.status == "IN_PROGRESS"
    events = (
        await session.execute(
            OutboxEvent.__table__.select().where(OutboxEvent.event_type == "TaskStatusChanged")
        )
    ).fetchall()
    assert len(events) == 1
    assert events[0].payload["old_status"] == "TODO"
    assert events[0].payload["new_status"] == "IN_PROGRESS"


async def test_change_task_status_rejects_invalid_status(session):
    project = await create_project(session, CreateProjectCommand(name="P", owner_id=uuid.uuid4()))
    task = await create_task(session, CreateTaskCommand(project_id=project.id, title="T"))

    with pytest.raises(InvalidStatusError):
        await change_task_status(session, ChangeTaskStatusCommand(task_id=task.id, new_status="BOGUS"))


async def test_change_task_status_raises_for_missing_task(session):
    with pytest.raises(TaskNotFoundError):
        await change_task_status(
            session, ChangeTaskStatusCommand(task_id=uuid.uuid4(), new_status="DONE")
        )
