"""Domain events written to the outbox. Names match outbox_events.event_type."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ProjectCreated(BaseModel):
    event_type: Literal["ProjectCreated"] = "ProjectCreated"
    project_id: UUID
    name: str
    owner_id: UUID
    created_at: datetime


class TaskCreated(BaseModel):
    event_type: Literal["TaskCreated"] = "TaskCreated"
    task_id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: str
    assignee_id: UUID | None
    created_at: datetime
    # severity defaults to "low" for every task (see create_task) — not
    # mandatory to pick one, but always a concrete value once stored, never
    # null. trigger_type/external_reporter stay null unless the task came in
    # via the gRPC IssueIntake service (see grpc_server/issue_intake_servicer.py).
    severity: str
    trigger_type: str | None = None
    external_reporter: str | None = None


class TaskSeverityChanged(BaseModel):
    event_type: Literal["TaskSeverityChanged"] = "TaskSeverityChanged"
    task_id: UUID
    project_id: UUID
    old_severity: str
    new_severity: str
    changed_at: datetime


class TaskStatusChanged(BaseModel):
    event_type: Literal["TaskStatusChanged"] = "TaskStatusChanged"
    task_id: UUID
    project_id: UUID
    old_status: str
    new_status: str
    changed_at: datetime


class TaskAssigned(BaseModel):
    event_type: Literal["TaskAssigned"] = "TaskAssigned"
    task_id: UUID
    project_id: UUID
    old_assignee_id: UUID | None
    new_assignee_id: UUID | None
    changed_at: datetime


class TaskDeleted(BaseModel):
    event_type: Literal["TaskDeleted"] = "TaskDeleted"
    task_id: UUID
    project_id: UUID
    assignee_id: UUID | None
    deleted_at: datetime


class ProjectDeleted(BaseModel):
    event_type: Literal["ProjectDeleted"] = "ProjectDeleted"
    project_id: UUID
    # Captured before the cascade delete, since by the time the projector
    # processes this event the tasks (and their assignee_id) are already
    # gone from Postgres — nothing left to recompute workload from otherwise.
    affected_assignee_ids: list[UUID]
    deleted_at: datetime


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
