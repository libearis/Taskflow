import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.models import Project, Task
from app.command.repository import ProjectRepository, TaskRepository
from app.domain.events import (
    ProjectCreated,
    ProjectDeleted,
    TaskAssigned,
    TaskCreated,
    TaskDeleted,
    TaskSeverityChanged,
    TaskStatusChanged,
    now_utc,
)
from app.outbox.writer import write_event

VALID_STATUSES = ("TODO", "IN_PROGRESS", "DONE")
VALID_SEVERITIES = ("low", "medium", "high")

# Fixed, well-known IDs for the auto-provisioned project that external
# gRPC-reported issues (see grpc_server/issue_intake_servicer.py) land in.
# Matched by ID rather than by name so renaming the project later can't
# silently break the lookup and spawn a duplicate.
EXTERNAL_REPORTS_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
EXTERNAL_REPORTS_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e0")
EXTERNAL_REPORTS_PROJECT_NAME = "External Reports"


class InvalidStatusError(ValueError):
    pass


class InvalidSeverityError(ValueError):
    pass


class TaskNotFoundError(ValueError):
    pass


class ProjectNotFoundError(ValueError):
    pass


@dataclass
class CreateProjectCommand:
    name: str
    owner_id: uuid.UUID


@dataclass
class CreateTaskCommand:
    project_id: uuid.UUID
    title: str
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    severity: str | None = None
    trigger_type: str | None = None
    external_reporter: str | None = None


@dataclass
class CreateExternalIssueCommand:
    title: str
    description: str | None
    severity: str
    trigger_type: str
    external_reporter: str


@dataclass
class ChangeTaskStatusCommand:
    task_id: uuid.UUID
    new_status: str


@dataclass
class AssignTaskCommand:
    task_id: uuid.UUID
    assignee_id: uuid.UUID | None


@dataclass
class ChangeTaskSeverityCommand:
    task_id: uuid.UUID
    severity: str


@dataclass
class DeleteTaskCommand:
    task_id: uuid.UUID


@dataclass
class DeleteProjectCommand:
    project_id: uuid.UUID


async def create_project(session: AsyncSession, cmd: CreateProjectCommand) -> Project:
    repo = ProjectRepository(session)
    project = await repo.add(Project(name=cmd.name, owner_id=cmd.owner_id))

    event = ProjectCreated(
        project_id=project.id,
        name=project.name,
        owner_id=project.owner_id,
        created_at=now_utc(),
    )
    await write_event(session, aggregate_type="project", aggregate_id=project.id, event=event)

    await session.commit()
    await session.refresh(project)
    return project


async def create_task(session: AsyncSession, cmd: CreateTaskCommand) -> Task:
    # Not mandatory to pick a severity — defaults to "low" rather than
    # staying null, so every task has a concrete value to render/filter on.
    severity = cmd.severity or "low"
    if severity not in VALID_SEVERITIES:
        raise InvalidSeverityError(f"Invalid severity: {severity}")

    repo = TaskRepository(session)
    task = await repo.add(
        Task(
            project_id=cmd.project_id,
            title=cmd.title,
            description=cmd.description,
            status="TODO",
            assignee_id=cmd.assignee_id,
            severity=severity,
            trigger_type=cmd.trigger_type,
            external_reporter=cmd.external_reporter,
        )
    )

    event = TaskCreated(
        task_id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        assignee_id=task.assignee_id,
        created_at=now_utc(),
        severity=task.severity,
        trigger_type=task.trigger_type,
        external_reporter=task.external_reporter,
    )
    await write_event(session, aggregate_type="task", aggregate_id=task.id, event=event)

    await session.commit()
    await session.refresh(task)
    return task


async def _get_or_create_external_reports_project(session: AsyncSession) -> Project:
    repo = ProjectRepository(session)
    project = await repo.get(EXTERNAL_REPORTS_PROJECT_ID)
    if project is not None:
        return project

    project = Project(
        id=EXTERNAL_REPORTS_PROJECT_ID,
        name=EXTERNAL_REPORTS_PROJECT_NAME,
        owner_id=EXTERNAL_REPORTS_OWNER_ID,
    )
    try:
        project = await repo.add(project)
    except IntegrityError:
        # EXTERNAL_REPORTS_PROJECT_ID is a fixed constant, so its uniqueness
        # is already guaranteed by the primary key — this only fires if
        # something else won the exact same get()-then-add() race between
        # our check above and this insert (e.g. two requests landing back to
        # back right after a dev-server hot-reload restart). Not a real
        # concurrency scenario in production; cheap to not crash on anyway.
        await session.rollback()
        project = await repo.get(EXTERNAL_REPORTS_PROJECT_ID)
        assert project is not None, "insert conflicted but the row isn't there"
        return project

    event = ProjectCreated(
        project_id=project.id,
        name=project.name,
        owner_id=project.owner_id,
        created_at=now_utc(),
    )
    await write_event(session, aggregate_type="project", aggregate_id=project.id, event=event)
    # Not committing here — the caller commits once, together with the task
    # this project is being created to hold, so both land atomically.
    return project


async def create_external_issue(session: AsyncSession, cmd: CreateExternalIssueCommand) -> Task:
    """Entry point for the gRPC IssueIntake service — an issue reported by an
    external system becomes a Task under a dedicated, auto-provisioned
    project, going through the exact same outbox path as a UI-created task."""
    if cmd.severity not in VALID_SEVERITIES:
        raise InvalidSeverityError(f"Invalid severity: {cmd.severity}")

    project = await _get_or_create_external_reports_project(session)

    return await create_task(
        session,
        CreateTaskCommand(
            project_id=project.id,
            title=cmd.title,
            description=cmd.description,
            severity=cmd.severity,
            trigger_type=cmd.trigger_type,
            external_reporter=cmd.external_reporter,
        ),
    )


async def change_task_status(session: AsyncSession, cmd: ChangeTaskStatusCommand) -> Task:
    if cmd.new_status not in VALID_STATUSES:
        raise InvalidStatusError(f"Invalid status: {cmd.new_status}")

    repo = TaskRepository(session)
    task = await repo.get_for_update(cmd.task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {cmd.task_id} not found")

    old_status = task.status
    task.status = cmd.new_status
    await session.flush()

    event = TaskStatusChanged(
        task_id=task.id,
        project_id=task.project_id,
        old_status=old_status,
        new_status=task.status,
        changed_at=now_utc(),
    )
    await write_event(session, aggregate_type="task", aggregate_id=task.id, event=event)

    await session.commit()
    await session.refresh(task)
    return task


async def assign_task(session: AsyncSession, cmd: AssignTaskCommand) -> Task:
    repo = TaskRepository(session)
    task = await repo.get_for_update(cmd.task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {cmd.task_id} not found")

    old_assignee_id = task.assignee_id
    task.assignee_id = cmd.assignee_id
    await session.flush()

    event = TaskAssigned(
        task_id=task.id,
        project_id=task.project_id,
        old_assignee_id=old_assignee_id,
        new_assignee_id=task.assignee_id,
        changed_at=now_utc(),
    )
    await write_event(session, aggregate_type="task", aggregate_id=task.id, event=event)

    await session.commit()
    await session.refresh(task)
    return task


async def change_task_severity(session: AsyncSession, cmd: ChangeTaskSeverityCommand) -> Task:
    if cmd.severity not in VALID_SEVERITIES:
        raise InvalidSeverityError(f"Invalid severity: {cmd.severity}")

    repo = TaskRepository(session)
    task = await repo.get_for_update(cmd.task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {cmd.task_id} not found")

    old_severity = task.severity
    task.severity = cmd.severity
    await session.flush()

    event = TaskSeverityChanged(
        task_id=task.id,
        project_id=task.project_id,
        old_severity=old_severity,
        new_severity=task.severity,
        changed_at=now_utc(),
    )
    await write_event(session, aggregate_type="task", aggregate_id=task.id, event=event)

    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, cmd: DeleteTaskCommand) -> None:
    repo = TaskRepository(session)
    task = await repo.get_for_update(cmd.task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {cmd.task_id} not found")

    project_id, assignee_id = task.project_id, task.assignee_id
    await repo.delete(task)
    await session.flush()

    event = TaskDeleted(
        task_id=cmd.task_id,
        project_id=project_id,
        assignee_id=assignee_id,
        deleted_at=now_utc(),
    )
    await write_event(session, aggregate_type="task", aggregate_id=cmd.task_id, event=event)

    await session.commit()


async def delete_project(session: AsyncSession, cmd: DeleteProjectCommand) -> None:
    project_repo = ProjectRepository(session)
    task_repo = TaskRepository(session)

    project = await project_repo.get(cmd.project_id)
    if project is None:
        raise ProjectNotFoundError(f"Project {cmd.project_id} not found")

    tasks = await task_repo.list_by_project(cmd.project_id)
    # Captured now — after the cascade delete below, these tasks (and their
    # assignee_id) no longer exist in Postgres for the projector to read.
    affected_assignee_ids = list({t.assignee_id for t in tasks if t.assignee_id is not None})

    for task in tasks:
        await task_repo.delete(task)
    await project_repo.delete(project)
    await session.flush()

    event = ProjectDeleted(
        project_id=cmd.project_id,
        affected_assignee_ids=affected_assignee_ids,
        deleted_at=now_utc(),
    )
    await write_event(session, aggregate_type="project", aggregate_id=cmd.project_id, event=event)

    await session.commit()
