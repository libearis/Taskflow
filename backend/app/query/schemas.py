from datetime import datetime

from pydantic import BaseModel


class BoardTask(BaseModel):
    task_id: str
    title: str
    assignee_id: str | None = None
    assignee_name: str | None = None
    severity: str | None = None
    trigger_type: str | None = None
    external_reporter: str | None = None


class ProjectSummary(BaseModel):
    project_id: str
    project_name: str
    last_updated: datetime


class ProjectBoard(BaseModel):
    project_id: str
    project_name: str
    columns: dict[str, list[BoardTask]]
    last_updated: datetime


class ProjectWorkload(BaseModel):
    project_id: str
    project_name: str
    count: int


class UserWorkload(BaseModel):
    user_id: str
    user_name: str
    active_tasks: int
    tasks_by_project: list[ProjectWorkload]
    last_updated: datetime
