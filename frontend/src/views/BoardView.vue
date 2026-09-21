<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";

import type { Severity } from "@/api/rest";
import { useBoardStore } from "@/stores/board";
import { useConfirmStore } from "@/stores/confirm";
import { useProjectsStore } from "@/stores/projects";

const props = defineProps<{ projectId: string }>();

const board = useBoardStore();
const projects = useProjectsStore();
const confirmDialog = useConfirmStore();
const router = useRouter();
const newTaskTitle = ref("");
const newTaskSeverity = ref<Severity>("low");
const adding = ref(false);
const deletingProject = ref(false);
const SEVERITIES: Severity[] = ["low", "medium", "high"];

const COLUMNS: { key: string; label: string }[] = [
  { key: "TODO", label: "To Do" },
  { key: "IN_PROGRESS", label: "In Progress" },
  { key: "DONE", label: "Done" },
];
const COLUMN_ORDER = COLUMNS.map((c) => c.key);

onMounted(async () => {
  await board.load(props.projectId);
  board.subscribeLive(props.projectId);
});

onUnmounted(() => {
  board.stop();
});

async function addTask() {
  const title = newTaskTitle.value.trim();
  if (!title) return;
  adding.value = true;
  try {
    const task = await projects.addTask(props.projectId, title, undefined, newTaskSeverity.value);
    newTaskTitle.value = "";
    newTaskSeverity.value = "low";
    // The gRPC stream only carries status-change events, not new tasks — so
    // this polls REST until the outbox projector has synced it into Mongo,
    // instead of the task silently never appearing (see stores/board.ts).
    void board.waitUntilTaskVisible(props.projectId, task.id);
  } finally {
    adding.value = false;
  }
}

async function handleChangeStatus(taskId: string, newStatus: string) {
  try {
    await board.changeStatus(props.projectId, taskId, newStatus);
  } catch {
    // board.actionError is already set — surfaced in the template below.
  }
}

async function handleChangeSeverity(taskId: string, severity: Severity) {
  try {
    await board.changeSeverity(taskId, severity);
  } catch {
    // board.actionError is already set — surfaced in the template below.
  }
}

async function handleDeleteTask(taskId: string, title: string) {
  const ok = await confirmDialog.confirm(`Hapus task "${title}"? Aksi ini tidak bisa dibatalkan.`, {
    title: "Hapus Task",
    confirmLabel: "Hapus",
    danger: true,
  });
  if (!ok) return;
  try {
    await board.deleteTask(taskId);
  } catch {
    // board.actionError is already set — surfaced in the template below.
  }
}

async function handleDeleteProject() {
  const name = board.board?.project_name ?? "project ini";
  const ok = await confirmDialog.confirm(
    `Hapus "${name}" beserta semua task-nya? Aksi ini tidak bisa dibatalkan.`,
    { title: "Hapus Project", confirmLabel: "Hapus", danger: true }
  );
  if (!ok) return;
  deletingProject.value = true;
  try {
    await projects.remove(props.projectId);
    router.push({ name: "projects" });
  } catch {
    deletingProject.value = false;
    await confirmDialog.alert("Gagal menghapus project.", { title: "Gagal", danger: true });
  }
}

function nextStatus(current: string): string | null {
  const idx = COLUMN_ORDER.indexOf(current);
  return idx >= 0 && idx < COLUMN_ORDER.length - 1 ? COLUMN_ORDER[idx + 1] : null;
}

function prevStatus(current: string): string | null {
  const idx = COLUMN_ORDER.indexOf(current);
  return idx > 0 ? COLUMN_ORDER[idx - 1] : null;
}

function columnLabel(key: string | null): string {
  return COLUMNS.find((c) => c.key === key)?.label ?? "";
}

function initials(name: string | null): string {
  if (!name) return "?";
  return name.slice(0, 2).toUpperCase();
}

// Tasks created via the UI never set severity — treat that the same as
// "low" visually rather than showing no badge at all, so severity reads as
// one consistent scale across every card instead of only appearing for
// externally-reported issues.
function severityLabel(severity: string | null): string {
  const s = severity ?? "low";
  return s.charAt(0).toUpperCase() + s.slice(1);
}
</script>

<template>
  <section class="board-page">
    <header class="board-header">
      <div class="board-title-row">
        <h1 class="board-title">{{ board.board?.project_name ?? "Board" }}</h1>
        <span class="live-indicator" :class="{ on: board.liveConnected }">
          <span class="live-dot" />
          {{ board.liveConnected ? "Live" : "Connecting…" }}
        </span>
        <button class="btn-danger-ghost" :disabled="deletingProject" @click="handleDeleteProject">
          {{ deletingProject ? "Menghapus…" : "Hapus Project" }}
        </button>
      </div>
      <p v-if="board.syncingNewTask" class="sync-hint">
        Menyinkronkan task baru ke board… (outbox → projector → read model)
      </p>
      <p v-if="board.actionError" class="action-error">{{ board.actionError }}</p>
    </header>

    <form @submit.prevent="addTask" class="add-task-form">
      <input
        v-model="newTaskTitle"
        class="add-task-input"
        placeholder="Judul task baru…"
        :disabled="adding"
      />
      <select v-model="newTaskSeverity" class="severity-select" :disabled="adding" title="Severity (opsional, default Low)">
        <option v-for="s in SEVERITIES" :key="s" :value="s">{{ severityLabel(s) }}</option>
      </select>
      <button type="submit" class="btn-primary" :disabled="adding || !newTaskTitle.trim()">
        {{ adding ? "Menambah…" : "Tambah Task" }}
      </button>
    </form>

    <p v-if="board.loading" class="state-message">Memuat board…</p>
    <p v-else-if="board.error" class="state-message state-message--error">{{ board.error }}</p>

    <div v-else class="columns">
      <div v-for="col in COLUMNS" :key="col.key" class="column">
        <div class="column-header">
          <h2 class="column-title">{{ col.label }}</h2>
          <span class="column-count">{{ (board.board?.columns[col.key] ?? []).length }}</span>
        </div>

        <div class="column-body">
          <p v-if="!(board.board?.columns[col.key] ?? []).length" class="column-empty">
            Belum ada task
          </p>

          <article
            v-for="task in board.board?.columns[col.key] ?? []"
            :key="task.task_id"
            class="task-card"
            :class="`severity-${task.severity ?? 'low'}`"
          >
            <div class="task-card-top">
              <p class="task-title">{{ task.title }}</p>
              <button
                class="btn-delete-task"
                title="Hapus task"
                @click="handleDeleteTask(task.task_id, task.title)"
              >
                ×
              </button>
            </div>
            <div class="task-meta">
              <select
                class="severity-select"
                :class="`severity-${task.severity ?? 'low'}`"
                :value="task.severity ?? 'low'"
                title="Ubah severity"
                @change="handleChangeSeverity(task.task_id, ($event.target as HTMLSelectElement).value as Severity)"
              >
                <option v-for="s in SEVERITIES" :key="s" :value="s">{{ severityLabel(s) }}</option>
              </select>
              <span v-if="task.external_reporter" class="external-badge" title="Dilaporkan lewat gRPC IssueIntake">
                Dilaporkan oleh {{ task.external_reporter }}
              </span>
            </div>
            <div class="task-footer">
              <span class="task-assignee" :title="task.assignee_name ?? 'Belum di-assign'">
                {{ initials(task.assignee_name) }}
              </span>
              <div class="task-move-actions">
                <button
                  v-if="prevStatus(col.key)"
                  class="btn-move"
                  @click="handleChangeStatus(task.task_id, prevStatus(col.key)!)"
                >
                  ← {{ columnLabel(prevStatus(col.key)) }}
                </button>
                <button
                  v-if="nextStatus(col.key)"
                  class="btn-move"
                  @click="handleChangeStatus(task.task_id, nextStatus(col.key)!)"
                >
                  {{ columnLabel(nextStatus(col.key)) }} →
                </button>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.board-page {
  max-width: 1100px;
  margin: 0 auto;
}

.board-header {
  margin-bottom: 1.5rem;
}

.board-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.board-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #101828;
  margin: 0;
  letter-spacing: -0.01em;
  flex: 1;
}

.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #98a2b3;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  background: #f2f4f7;
}

.live-indicator.on {
  color: #067647;
  background: #ecfdf3;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #98a2b3;
}

.live-indicator.on .live-dot {
  background: #12b76a;
}

.btn-danger-ghost {
  font-size: 0.8rem;
  font-weight: 600;
  color: #b42318;
  background: none;
  border: 1px solid #fda29b;
  border-radius: 6px;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-danger-ghost:hover:not(:disabled) {
  background: #fef3f2;
}

.btn-danger-ghost:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sync-hint {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: #b54708;
  font-weight: 500;
}

.action-error {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: #b42318;
  font-weight: 500;
}

.add-task-form {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 1.75rem;
}

.add-task-input {
  flex: 1;
  padding: 0.65rem 0.9rem;
  font-size: 0.95rem;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: white;
  outline: none;
  transition: border-color 0.15s;
}

.add-task-input:focus {
  border-color: #7f56d9;
  box-shadow: 0 0 0 3px rgba(127, 86, 217, 0.12);
}

.btn-primary {
  padding: 0.65rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
  background: #7f56d9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) {
  background: #6941c6;
}

.btn-primary:disabled {
  background: #d0d5dd;
  cursor: not-allowed;
}

.add-task-form .severity-select {
  padding: 0.65rem 0.7rem;
  font-size: 0.9rem;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: white;
  color: #344054;
  cursor: pointer;
}

.state-message {
  font-size: 0.95rem;
  color: #667085;
}

.state-message--error {
  color: #b42318;
}

.columns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 800px) {
  .columns {
    grid-template-columns: 1fr;
  }
}

.column {
  background: #f9fafb;
  border-radius: 10px;
  padding: 0.9rem;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0.25rem;
}

.column-title {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #475467;
  margin: 0;
}

.column-count {
  font-size: 0.75rem;
  font-weight: 700;
  color: #475467;
  background: #e4e7ec;
  border-radius: 999px;
  padding: 0.1rem 0.55rem;
  min-width: 1.5rem;
  text-align: center;
}

.column-body {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.column-empty {
  font-size: 0.85rem;
  color: #98a2b3;
  text-align: center;
  padding: 1.5rem 0;
  margin: 0;
}

.task-card {
  background: white;
  border: 1px solid #e4e7ec;
  border-left: 3px solid #d0d5dd;
  border-radius: 8px;
  padding: 0.75rem 0.85rem;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

/* Severity reads off the whole card (subtle tint + left accent), kept
   muted on purpose — this is a status cue on a work item, not an alert. */
.task-card.severity-low {
  border-left-color: #98a2b3;
}

.task-card.severity-medium {
  background: #fefbf2;
  border-left-color: #dc9d1f;
}

.task-card.severity-high {
  background: #fdf5f4;
  border-left-color: #b3392c;
}

.task-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.4rem;
}

.task-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #101828;
  margin: 0 0 0.6rem;
  line-height: 1.4;
}

.btn-delete-task {
  font-size: 1rem;
  line-height: 1;
  color: #98a2b3;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0 0.2rem;
  flex-shrink: 0;
}

.btn-delete-task:hover {
  color: #b42318;
}

.task-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.6rem;
}

.external-badge {
  font-size: 0.7rem;
  color: #98a2b3;
  font-style: italic;
}

.task-meta .severity-select {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 0.1rem 0.3rem;
  border: none;
  background: transparent;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}

.task-meta .severity-select.severity-low {
  color: #667085;
}

.task-meta .severity-select.severity-medium {
  color: #b54708;
}

.task-meta .severity-select.severity-high {
  color: #b42318;
}

.task-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.task-move-actions {
  display: flex;
  gap: 0.6rem;
}

.task-assignee {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 50%;
  background: #eef4ff;
  color: #3538cd;
  font-size: 0.65rem;
  font-weight: 700;
  flex-shrink: 0;
}

.btn-move {
  font-size: 0.75rem;
  font-weight: 600;
  color: #6941c6;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  text-align: right;
}

.btn-move:hover {
  text-decoration: underline;
}
</style>
