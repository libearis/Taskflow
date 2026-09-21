from app.query.repository import BoardReadRepository, WorkloadReadRepository
from app.query.schemas import ProjectBoard, ProjectSummary, UserWorkload


async def get_board(project_id: str) -> ProjectBoard | None:
    return await BoardReadRepository().get_board(project_id)


async def list_projects() -> list[ProjectSummary]:
    return await BoardReadRepository().list_projects()


async def get_user_workload(user_id: str) -> UserWorkload | None:
    return await WorkloadReadRepository().get_workload(user_id)
