import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.command.models import Project, Task


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project

    async def get(self, project_id: uuid.UUID) -> Project | None:
        return await self.session.get(Project, project_id)

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        return task

    async def get(self, task_id: uuid.UUID) -> Task | None:
        return await self.session.get(Task, task_id)

    async def get_for_update(self, task_id: uuid.UUID) -> Task | None:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> list[Task]:
        result = await self.session.execute(select(Task).where(Task.project_id == project_id))
        return list(result.scalars().all())

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
