<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { useConfirmStore } from "@/stores/confirm";
import { useProjectsStore } from "@/stores/projects";

const store = useProjectsStore();
const confirmDialog = useConfirmStore();
const router = useRouter();

const name = ref("");
const ownerId = ref(crypto.randomUUID());
const creating = ref(false);

onMounted(() => {
  store.fetchAll();
});

async function submit() {
  if (!name.value.trim()) return;
  creating.value = true;
  try {
    const project = await store.add(name.value.trim(), ownerId.value);
    name.value = "";
    router.push({ name: "board", params: { projectId: project.id } });
  } finally {
    creating.value = false;
  }
}

async function handleDelete(projectId: string, name: string) {
  const ok = await confirmDialog.confirm(
    `Hapus "${name}" beserta semua task-nya? Aksi ini tidak bisa dibatalkan.`,
    { title: "Hapus Project", confirmLabel: "Hapus", danger: true }
  );
  if (!ok) return;
  try {
    await store.remove(projectId);
  } catch {
    await confirmDialog.alert("Gagal menghapus project.", { title: "Gagal", danger: true });
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("id-ID", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<template>
  <section class="projects-page">
    <header class="page-header">
      <h1 class="page-title">Projects</h1>
      <p class="page-subtitle">Pilih project buat lihat board-nya, atau bikin baru di bawah.</p>
    </header>

    <form @submit.prevent="submit" class="create-form">
      <input
        v-model="name"
        class="create-input"
        placeholder="Nama project baru…"
        :disabled="creating"
      />
      <button type="submit" class="btn-primary" :disabled="creating || !name.trim()">
        {{ creating ? "Membuat…" : "Buat Project" }}
      </button>
    </form>

    <p v-if="store.loading" class="state-message">Memuat daftar project…</p>
    <p v-else-if="store.error" class="state-message state-message--error">{{ store.error }}</p>

    <div v-else-if="store.projects.length" class="project-list">
      <router-link
        v-for="p in store.projects"
        :key="p.project_id"
        :to="{ name: 'board', params: { projectId: p.project_id } }"
        class="project-card"
      >
        <span class="project-icon">{{ p.project_name.slice(0, 1).toUpperCase() }}</span>
        <span class="project-info">
          <span class="project-name">{{ p.project_name }}</span>
          <span class="project-meta">Diupdate {{ formatDate(p.last_updated) }}</span>
        </span>
        <button
          class="btn-delete-project"
          title="Hapus project"
          @click.stop.prevent="handleDelete(p.project_id, p.project_name)"
        >
          ×
        </button>
        <span class="project-arrow">→</span>
      </router-link>
    </div>

    <div v-else class="empty-state">
      <p class="empty-title">Belum ada project</p>
      <p class="empty-subtitle">Buat satu lewat form di atas untuk masuk ke board-nya.</p>
    </div>
  </section>
</template>

<style scoped>
.projects-page {
  max-width: 720px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.75rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #101828;
  margin: 0 0 0.35rem;
  letter-spacing: -0.01em;
}

.page-subtitle {
  font-size: 0.95rem;
  color: #667085;
  margin: 0;
}

.create-form {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 2rem;
}

.create-input {
  flex: 1;
  padding: 0.7rem 1rem;
  font-size: 0.95rem;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: white;
  outline: none;
  transition: border-color 0.15s;
}

.create-input:focus {
  border-color: #7f56d9;
  box-shadow: 0 0 0 3px rgba(127, 86, 217, 0.12);
}

.btn-primary {
  padding: 0.7rem 1.4rem;
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

.state-message {
  font-size: 0.95rem;
  color: #667085;
}

.state-message--error {
  color: #b42318;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.project-card {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.9rem 1rem;
  background: white;
  border: 1px solid #e4e7ec;
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.project-card:hover {
  border-color: #7f56d9;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
}

.project-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 8px;
  background: #f4ebff;
  color: #6941c6;
  font-size: 1.1rem;
  font-weight: 700;
  flex-shrink: 0;
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}

.project-name {
  font-size: 1rem;
  font-weight: 600;
  color: #101828;
}

.project-meta {
  font-size: 0.8rem;
  color: #98a2b3;
  font-family: ui-monospace, "SF Mono", Consolas, monospace;
}

.project-arrow {
  font-size: 1.1rem;
  color: #98a2b3;
  flex-shrink: 0;
}

.btn-delete-project {
  font-size: 1.2rem;
  line-height: 1;
  color: #98a2b3;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  flex-shrink: 0;
  border-radius: 6px;
}

.btn-delete-project:hover {
  color: #b42318;
  background: #fef3f2;
}

.empty-state {
  text-align: center;
  padding: 3rem 1.5rem;
  background: #f9fafb;
  border-radius: 10px;
  border: 1px dashed #d0d5dd;
}

.empty-title {
  font-size: 1rem;
  font-weight: 600;
  color: #344054;
  margin: 0 0 0.35rem;
}

.empty-subtitle {
  font-size: 0.875rem;
  color: #98a2b3;
  margin: 0;
}
</style>
