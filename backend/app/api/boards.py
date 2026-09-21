import uuid

from fastapi import APIRouter, HTTPException

from app.query.handlers import get_board, get_user_workload, list_projects
from app.query.schemas import ProjectBoard, ProjectSummary, UserWorkload

router = APIRouter(tags=["boards"])


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects_endpoint() -> list[ProjectSummary]:
    return await list_projects()


@router.get("/projects/{project_id}/board", response_model=ProjectBoard)
async def get_project_board(project_id: uuid.UUID) -> ProjectBoard:
    board = await get_board(str(project_id))
    if board is None:
        raise HTTPException(
            status_code=404,
            detail="Board not found yet — it may not have been projected from the outbox yet.",
        )
    return board


@router.get("/users/{user_id}/workload", response_model=UserWorkload)
async def get_workload(user_id: uuid.UUID) -> UserWorkload:
    workload = await get_user_workload(str(user_id))
    if workload is None:
        raise HTTPException(status_code=404, detail="Workload not found yet.")
    return workload
