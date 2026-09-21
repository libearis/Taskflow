from app.mongo import project_boards, user_workload
from app.query.schemas import ProjectBoard, ProjectSummary, UserWorkload


class BoardReadRepository:
    async def get_board(self, project_id: str) -> ProjectBoard | None:
        doc = await project_boards.find_one({"_id": project_id})
        if doc is None:
            return None
        return ProjectBoard(
            project_id=doc["_id"],
            project_name=doc["project_name"],
            columns=doc["columns"],
            last_updated=doc["last_updated"],
        )

    async def list_projects(self) -> list[ProjectSummary]:
        # Reads from the read model (Mongo), same as everything else on the
        # query side — a project only appears here once ProjectCreated has
        # been projected, same eventual-consistency gap as the board itself.
        cursor = project_boards.find(
            {}, {"_id": 1, "project_name": 1, "last_updated": 1}
        ).sort("last_updated", -1)
        return [
            ProjectSummary(
                project_id=doc["_id"],
                project_name=doc["project_name"],
                last_updated=doc["last_updated"],
            )
            async for doc in cursor
        ]


class WorkloadReadRepository:
    async def get_workload(self, user_id: str) -> UserWorkload | None:
        doc = await user_workload.find_one({"_id": user_id})
        if doc is None:
            return None
        return UserWorkload(
            user_id=doc["_id"],
            user_name=doc["user_name"],
            active_tasks=doc["active_tasks"],
            tasks_by_project=doc["tasks_by_project"],
            last_updated=doc["last_updated"],
        )
