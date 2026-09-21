import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.handlers import (
    AssignTaskCommand,
    ChangeTaskSeverityCommand,
    ChangeTaskStatusCommand,
    CreateTaskCommand,
    DeleteTaskCommand,
    InvalidSeverityError,
    InvalidStatusError,
    TaskNotFoundError,
    assign_task,
    change_task_severity,
    change_task_status,
    create_task,
    delete_task,
)
from app.db import get_session

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    project_id: uuid.UUID
    title: str
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    # Optional — defaults to "low" server-side if omitted (see create_task).
    severity: str | None = None


class ChangeStatusRequest(BaseModel):
    status: str


class ChangeSeverityRequest(BaseModel):
    severity: str


class AssignRequest(BaseModel):
    assignee_id: uuid.UUID | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    assignee_id: uuid.UUID | None
    severity: str
    trigger_type: str | None
    external_reporter: str | None

    model_config = {"from_attributes": True}


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task_endpoint(
    body: CreateTaskRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await create_task(
            session,
            CreateTaskCommand(
                project_id=body.project_id,
                title=body.title,
                description=body.description,
                assignee_id=body.assignee_id,
                severity=body.severity,
            ),
        )
    except InvalidSeverityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}/status", response_model=TaskResponse)
async def change_task_status_endpoint(
    task_id: uuid.UUID,
    body: ChangeStatusRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await change_task_status(
            session, ChangeTaskStatusCommand(task_id=task_id, new_status=body.status)
        )
    except InvalidStatusError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}/severity", response_model=TaskResponse)
async def change_task_severity_endpoint(
    task_id: uuid.UUID,
    body: ChangeSeverityRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await change_task_severity(
            session, ChangeTaskSeverityCommand(task_id=task_id, severity=body.severity)
        )
    except InvalidSeverityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}/assignee", response_model=TaskResponse)
async def assign_task_endpoint(
    task_id: uuid.UUID,
    body: AssignRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    try:
        task = await assign_task(
            session, AssignTaskCommand(task_id=task_id, assignee_id=body.assignee_id)
        )
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task_endpoint(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await delete_task(session, DeleteTaskCommand(task_id=task_id))
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
