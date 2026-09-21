import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.handlers import (
    CreateProjectCommand,
    DeleteProjectCommand,
    ProjectNotFoundError,
    create_project,
    delete_project,
)
from app.db import get_session

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    owner_id: uuid.UUID


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID

    model_config = {"from_attributes": True}


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project_endpoint(
    body: CreateProjectRequest,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    project = await create_project(
        session, CreateProjectCommand(name=body.name, owner_id=body.owner_id)
    )
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard delete — removes the project AND all its tasks from Postgres in
    one transaction, then the outbox event removes the board doc from Mongo."""
    try:
        await delete_project(session, DeleteProjectCommand(project_id=project_id))
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
