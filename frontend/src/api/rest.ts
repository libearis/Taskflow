import axios from "axios";

export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

export interface Project {
  id: string;
  name: string;
  owner_id: string;
}

export interface ProjectSummary {
  project_id: string;
  project_name: string;
  last_updated: string;
}

export type Severity = "low" | "medium" | "high";

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: "TODO" | "IN_PROGRESS" | "DONE";
  assignee_id: string | null;
  severity: Severity;
  trigger_type: string | null;
  external_reporter: string | null;
}

export interface BoardTask {
  task_id: string;
  title: string;
  assignee_id: string | null;
  assignee_name: string | null;
  severity: Severity | null;
  trigger_type: string | null;
  external_reporter: string | null;
}

export interface ProjectBoard {
  project_id: string;
  project_name: string;
  columns: Record<string, BoardTask[]>;
  last_updated: string;
}

export interface UserWorkload {
  user_id: string;
  user_name: string;
  active_tasks: number;
  tasks_by_project: { project_id: string; project_name: string; count: number }[];
  last_updated: string;
}

export async function createProject(name: string, ownerId: string): Promise<Project> {
  const { data } = await httpClient.post<Project>("/projects", { name, owner_id: ownerId });
  return data;
}

export async function createTask(
  projectId: string,
  title: string,
  description?: string,
  assigneeId?: string,
  severity?: Severity
): Promise<Task> {
  const { data } = await httpClient.post<Task>("/tasks", {
    project_id: projectId,
    title,
    description: description ?? null,
    assignee_id: assigneeId ?? null,
    severity: severity ?? null,
  });
  return data;
}

export async function changeTaskStatus(taskId: string, status: string): Promise<Task> {
  const { data } = await httpClient.patch<Task>(`/tasks/${taskId}/status`, { status });
  return data;
}

export async function changeTaskSeverity(taskId: string, severity: Severity): Promise<Task> {
  const { data } = await httpClient.patch<Task>(`/tasks/${taskId}/severity`, { severity });
  return data;
}

export async function assignTask(taskId: string, assigneeId: string | null): Promise<Task> {
  const { data } = await httpClient.patch<Task>(`/tasks/${taskId}/assignee`, {
    assignee_id: assigneeId,
  });
  return data;
}

export async function deleteTask(taskId: string): Promise<void> {
  await httpClient.delete(`/tasks/${taskId}`);
}

export async function deleteProject(projectId: string): Promise<void> {
  await httpClient.delete(`/projects/${projectId}`);
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const { data } = await httpClient.get<ProjectSummary[]>("/projects");
  return data;
}

export async function getProjectBoard(projectId: string): Promise<ProjectBoard> {
  const { data } = await httpClient.get<ProjectBoard>(`/projects/${projectId}/board`);
  return data;
}

export async function getUserWorkload(userId: string): Promise<UserWorkload> {
  const { data } = await httpClient.get<UserWorkload>(`/users/${userId}/workload`);
  return data;
}
