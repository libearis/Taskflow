import { defineStore } from "pinia";

import { subscribeToBoardUpdates } from "@/api/boardStream";
import {
  changeTaskSeverity,
  changeTaskStatus,
  deleteTask as deleteTaskRequest,
  getProjectBoard,
  type BoardTask,
  type ProjectBoard,
  type Severity,
} from "@/api/rest";
import { useLoadingStore } from "@/stores/loading";

export const useBoardStore = defineStore("board", {
  state: () => ({
    board: null as ProjectBoard | null,
    loading: false,
    error: null as string | null,
    actionError: null as string | null,
    liveConnected: false,
    unsubscribe: null as (() => void) | null,
    syncingNewTask: false,
  }),

  actions: {
    // Retries a few times before giving up: a project you just created can
    // briefly 404 here too (ProjectCreated hasn't reached Mongo yet), same
    // eventual-consistency gap as a freshly created task.
    async load(projectId: string, maxAttempts = 6, intervalMs = 1000) {
      const loadingStore = useLoadingStore();
      this.loading = true;
      this.error = null;
      loadingStore.start();
      try {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          try {
            this.board = await getProjectBoard(projectId);
            this.error = null;
            return;
          } catch {
            if (attempt === maxAttempts - 1) {
              this.error = "Board belum tersedia — mungkin belum ter-sync dari outbox.";
            } else {
              await new Promise((resolve) => setTimeout(resolve, intervalMs));
            }
          }
        }
      } finally {
        this.loading = false;
        loadingStore.stop();
      }
    },

    subscribeLive(projectId: string) {
      this.unsubscribe?.();
      this.unsubscribe = subscribeToBoardUpdates(
        projectId,
        (update) => {
          this.liveConnected = true;
          this.applyUpdate(update.taskId, update.newStatus, update.title);
        },
        () => {
          this.liveConnected = false;
        }
      );
    },

    applyUpdate(taskId: string, newStatus: string, title: string) {
      if (!this.board) return;

      let moved: BoardTask | undefined;
      for (const column of Object.values(this.board.columns)) {
        const idx = column.findIndex((t) => t.task_id === taskId);
        if (idx !== -1) {
          moved = column.splice(idx, 1)[0];
          break;
        }
      }

      const task =
        moved ??
        ({
          task_id: taskId,
          title,
          assignee_id: null,
          assignee_name: null,
          severity: null,
          trigger_type: null,
          external_reporter: null,
        } satisfies BoardTask);
      if (!this.board.columns[newStatus]) this.board.columns[newStatus] = [];
      this.board.columns[newStatus].push(task);
    },

    async changeStatus(
      projectId: string,
      taskId: string,
      newStatus: string,
      maxAttempts = 8,
      intervalMs = 300
    ) {
      const loadingStore = useLoadingStore();
      this.actionError = null;
      loadingStore.start();
      try {
        await changeTaskStatus(taskId, newStatus);
      } catch (err: any) {
        // Without this catch, a failed PATCH here used to fail completely
        // silently (unhandled promise rejection, nothing shown on screen) —
        // clicking the button looked like it just did nothing.
        this.actionError =
          err?.response?.status === 404
            ? "Task ini sudah tidak ada (mungkin sudah dihapus atau data basi)."
            : "Gagal mengubah status task.";
        loadingStore.stop();
        throw err;
      }

      // The PATCH itself resolves almost instantly, but the board doesn't
      // actually show the move until the outbox projector catches up (up to
      // ~1s) and pushes it over the gRPC stream. Stopping the spinner right
      // after the PATCH used to leave a confusing gap — spinner gone, card
      // still in the old column, then it jumps a beat later. Keep the
      // spinner up across that whole gap instead, polling REST as a
      // fallback in case the stream event is missed for any reason.
      try {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          const inPlace = this.board?.columns[newStatus]?.some((t) => t.task_id === taskId);
          if (inPlace) return;
          await new Promise((resolve) => setTimeout(resolve, intervalMs));
          try {
            const board = await getProjectBoard(projectId);
            this.board = board;
            if (board.columns[newStatus]?.some((t) => t.task_id === taskId)) return;
          } catch {
            // keep retrying
          }
        }
      } finally {
        loadingStore.stop();
      }
    },

    async deleteTask(taskId: string) {
      const loadingStore = useLoadingStore();
      this.actionError = null;
      loadingStore.start();
      try {
        await deleteTaskRequest(taskId);
      } catch (err: any) {
        this.actionError =
          err?.response?.status === 404
            ? "Task ini sudah tidak ada (mungkin sudah dihapus atau data basi)."
            : "Gagal menghapus task.";
        throw err;
      } finally {
        loadingStore.stop();
      }
      // Delete is user-initiated and destructive — remove it from view right
      // away rather than waiting for the outbox/projector round-trip.
      if (this.board) {
        for (const column of Object.values(this.board.columns)) {
          const idx = column.findIndex((t) => t.task_id === taskId);
          if (idx !== -1) {
            column.splice(idx, 1);
            break;
          }
        }
      }
    },

    async changeSeverity(taskId: string, severity: Severity) {
      const loadingStore = useLoadingStore();
      this.actionError = null;
      loadingStore.start();
      try {
        await changeTaskSeverity(taskId, severity);
      } catch (err: any) {
        this.actionError =
          err?.response?.status === 404
            ? "Task ini sudah tidak ada (mungkin sudah dihapus atau data basi)."
            : "Gagal mengubah severity.";
        throw err;
      } finally {
        loadingStore.stop();
      }
      // Unlike a status move, this doesn't need the eventual-consistency gap
      // shown — it's a same-place metadata edit, so reflect it immediately
      // rather than waiting on the outbox/projector round-trip.
      if (this.board) {
        for (const column of Object.values(this.board.columns)) {
          const task = column.find((t) => t.task_id === taskId);
          if (task) {
            task.severity = severity;
            break;
          }
        }
      }
    },

    // The gRPC stream only forwards TaskStatusChanged events (see
    // backend/app/outbox/projector.py::_publish_stream_event) — a brand new
    // task never arrives over the stream, so without this, a created task
    // would silently sit in Mongo and never show up until a manual reload.
    // Polls REST every second until the outbox projector has synced the new
    // task into the board (or gives up after maxAttempts) — the gap stays
    // visible via `syncingNewTask` rather than being hidden.
    // Deliberately NOT wrapped in the global loading overlay: this runs in
    // the background after the create-task request already resolved, and
    // flashing a full-screen blocking overlay every second while it polls
    // would be worse UX than the small inline "syncing" hint it already has.
    async waitUntilTaskVisible(projectId: string, taskId: string, maxAttempts = 8, intervalMs = 1000) {
      this.syncingNewTask = true;
      try {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          await new Promise((resolve) => setTimeout(resolve, intervalMs));
          try {
            const board = await getProjectBoard(projectId);
            this.board = board;
            this.error = null;
            const found = Object.values(board.columns).some((col) =>
              col.some((t) => t.task_id === taskId)
            );
            if (found) return;
          } catch {
            // Board briefly 404-ing right after creation is expected — keep retrying.
          }
        }
      } finally {
        this.syncingNewTask = false;
      }
    },

    stop() {
      this.unsubscribe?.();
      this.unsubscribe = null;
    },
  },
});
