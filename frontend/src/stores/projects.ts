import { defineStore } from "pinia";

import {
  createProject,
  createTask,
  deleteProject,
  listProjects,
  type ProjectSummary,
  type Severity,
} from "@/api/rest";
import { useLoadingStore } from "@/stores/loading";

export const useProjectsStore = defineStore("projects", {
  state: () => ({
    projects: [] as ProjectSummary[],
    loading: false,
    error: null as string | null,
  }),

  actions: {
    // Reads from the query side (Mongo project_boards), so a just-created
    // project can briefly be missing here too — same eventual-consistency
    // gap as everything else backed by the outbox projector.
    async fetchAll() {
      const loadingStore = useLoadingStore();
      this.loading = true;
      this.error = null;
      loadingStore.start();
      try {
        this.projects = await listProjects();
      } catch {
        this.error = "Gagal memuat daftar project.";
      } finally {
        this.loading = false;
        loadingStore.stop();
      }
    },

    async add(name: string, ownerId: string) {
      const loadingStore = useLoadingStore();
      loadingStore.start();
      try {
        const project = await createProject(name, ownerId);
        // Optimistically show it right away — it won't be in the Mongo-backed
        // list yet (ProjectCreated hasn't been projected), so we prepend it
        // manually instead of waiting on a refetch.
        this.projects.unshift({
          project_id: project.id,
          project_name: project.name,
          last_updated: new Date().toISOString(),
        });
        return project;
      } finally {
        loadingStore.stop();
      }
    },

    async addTask(projectId: string, title: string, assigneeId?: string, severity?: Severity) {
      const loadingStore = useLoadingStore();
      loadingStore.start();
      try {
        return await createTask(projectId, title, undefined, assigneeId, severity);
      } finally {
        loadingStore.stop();
      }
    },

    async remove(projectId: string) {
      const loadingStore = useLoadingStore();
      loadingStore.start();
      try {
        await deleteProject(projectId);
        // Delete is a deliberate, user-initiated removal — unlike create/status
        // changes, hiding it immediately is what the user expects, not
        // something that needs the eventual-consistency gap made visible.
        this.projects = this.projects.filter((p) => p.project_id !== projectId);
      } finally {
        loadingStore.stop();
      }
    },
  },
});
