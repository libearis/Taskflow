"""Background worker: outbox_events (Postgres) -> project_boards / user_workload (Mongo)
-> in-process pub/sub (gRPC stream). Polling-based, no message broker.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.models import Project, Task
from app.config import settings
from app.db import async_session_factory
from app.grpc_server.pubsub import board_event_bus
from app.mongo import project_boards, user_workload
from app.outbox.models import OutboxEvent

logger = logging.getLogger(__name__)

COLUMN_STATUSES = ("TODO", "IN_PROGRESS", "DONE")


async def _fetch_pending_events(session: AsyncSession, limit: int = 50) -> list[OutboxEvent]:
    result = await session.execute(
        select(OutboxEvent)
        .where(OutboxEvent.status == "PENDING")
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(result.scalars().all())


async def _rebuild_project_board(session: AsyncSession, project_id) -> None:
    """Recompute the whole board doc for a project — idempotent by construction,
    so re-processing an event (e.g. after a crash) never corrupts the read model."""
    project = await session.get(Project, project_id)
    if project is None:
        return

    result = await session.execute(select(Task).where(Task.project_id == project_id))
    tasks = result.scalars().all()

    columns: dict[str, list[dict[str, Any]]] = {status: [] for status in COLUMN_STATUSES}
    for task in tasks:
        columns.setdefault(task.status, []).append(
            {
                "task_id": str(task.id),
                "title": task.title,
                "assignee_id": str(task.assignee_id) if task.assignee_id else None,
                "assignee_name": str(task.assignee_id) if task.assignee_id else None,
                "severity": task.severity,
                "trigger_type": task.trigger_type,
                "external_reporter": task.external_reporter,
            }
        )

    await project_boards.update_one(
        {"_id": str(project.id)},
        {
            "$set": {
                "project_name": project.name,
                "columns": columns,
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def _rebuild_user_workload(session: AsyncSession, user_id) -> None:
    if user_id is None:
        return

    result = await session.execute(select(Task).where(Task.assignee_id == user_id))
    tasks = result.scalars().all()
    active_tasks = [t for t in tasks if t.status != "DONE"]

    by_project: dict[str, dict[str, Any]] = {}
    for task in active_tasks:
        project = await session.get(Project, task.project_id)
        key = str(task.project_id)
        if key not in by_project:
            by_project[key] = {
                "project_id": key,
                "project_name": project.name if project else key,
                "count": 0,
            }
        by_project[key]["count"] += 1

    await user_workload.update_one(
        {"_id": str(user_id)},
        {
            "$set": {
                "user_name": str(user_id),
                "active_tasks": len(active_tasks),
                "tasks_by_project": list(by_project.values()),
                "last_updated": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def _delete_project_board(project_id) -> None:
    await project_boards.delete_one({"_id": str(project_id)})


async def _publish_stream_event(event: OutboxEvent) -> None:
    if event.event_type != "TaskStatusChanged":
        return
    payload = event.payload
    await board_event_bus.publish(
        str(payload["project_id"]),
        {
            "task_id": str(payload["task_id"]),
            "title": payload.get("title", ""),
            "old_status": payload.get("old_status", ""),
            "new_status": payload.get("new_status", ""),
            "assignee_id": payload.get("assignee_id"),
            "changed_at": payload.get("changed_at", ""),
        },
    )


async def process_event(session: AsyncSession, event: OutboxEvent) -> None:
    payload = event.payload

    if event.event_type == "ProjectCreated":
        await _rebuild_project_board(session, event.aggregate_id)
    elif event.event_type == "TaskCreated":
        await _rebuild_project_board(session, payload["project_id"])
        if payload.get("assignee_id"):
            await _rebuild_user_workload(session, payload["assignee_id"])
    elif event.event_type == "TaskStatusChanged":
        await _rebuild_project_board(session, payload["project_id"])
        task = await session.get(Task, event.aggregate_id)
        if task and task.assignee_id:
            await _rebuild_user_workload(session, task.assignee_id)
        await _publish_stream_event(event)
    elif event.event_type == "TaskSeverityChanged":
        await _rebuild_project_board(session, payload["project_id"])
    elif event.event_type == "TaskAssigned":
        await _rebuild_project_board(session, payload["project_id"])
        if payload.get("old_assignee_id"):
            await _rebuild_user_workload(session, payload["old_assignee_id"])
        if payload.get("new_assignee_id"):
            await _rebuild_user_workload(session, payload["new_assignee_id"])
    elif event.event_type == "TaskDeleted":
        # The task row is already gone from Postgres by the time this runs,
        # so rebuilding from current Postgres state naturally excludes it.
        await _rebuild_project_board(session, payload["project_id"])
        if payload.get("assignee_id"):
            await _rebuild_user_workload(session, payload["assignee_id"])
    elif event.event_type == "ProjectDeleted":
        await _delete_project_board(payload["project_id"])
        for assignee_id in payload.get("affected_assignee_ids", []):
            await _rebuild_user_workload(session, assignee_id)
    else:
        logger.warning("Unknown event_type=%s, skipping", event.event_type)


async def run_once(session: AsyncSession) -> int:
    """Process one batch of pending events. Returns the number processed."""
    events = await _fetch_pending_events(session)
    if not events:
        return 0

    for event in events:
        try:
            await process_event(session, event)
        except Exception:
            logger.exception("Failed to process outbox event %s", event.id)
            event.retry_count += 1
            if event.retry_count >= settings.projector_max_retries:
                event.status = "FAILED"
            continue
        event.status = "PROCESSED"
        event.processed_at = datetime.now(timezone.utc)

    await session.commit()
    return len(events)


async def run_forever(stop_event: asyncio.Event | None = None) -> None:
    logger.info("Outbox projector started (poll interval=%ss)", settings.projector_poll_interval_seconds)
    while stop_event is None or not stop_event.is_set():
        try:
            async with async_session_factory() as session:
                processed = await run_once(session)
        except Exception:
            # A transient DB/network blip (e.g. Postgres restarting) must not
            # take down the whole process — REST and the gRPC stream run in
            # the same TaskGroup as this loop, so an uncaught exception here
            # would kill them too. Log and retry on the next poll instead.
            logger.exception("Outbox projector iteration failed, will retry")
            await asyncio.sleep(settings.projector_poll_interval_seconds)
            continue
        if processed == 0:
            await asyncio.sleep(settings.projector_poll_interval_seconds)
