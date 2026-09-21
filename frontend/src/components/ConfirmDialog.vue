<script setup lang="ts">
import { useConfirmStore } from "@/stores/confirm";

const store = useConfirmStore();
</script>

<template>
  <Transition name="dialog-fade">
    <div v-if="store.visible" class="dialog-backdrop" @click.self="store.mode === 'alert' && store.respond(true)">
      <div class="dialog-card" role="alertdialog" aria-modal="true">
        <h2 class="dialog-title">{{ store.title }}</h2>
        <p class="dialog-message">{{ store.message }}</p>
        <div class="dialog-actions">
          <button
            v-if="store.mode === 'confirm'"
            class="btn-secondary"
            @click="store.respond(false)"
          >
            {{ store.cancelLabel }}
          </button>
          <button
            :class="store.danger ? 'btn-danger' : 'btn-primary'"
            @click="store.respond(true)"
          >
            {{ store.confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(16, 24, 40, 0.45);
  padding: 1rem;
}

.dialog-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  max-width: 420px;
  width: 100%;
  box-shadow: 0 20px 24px -4px rgba(16, 24, 40, 0.1), 0 8px 8px -4px rgba(16, 24, 40, 0.04);
}

.dialog-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #101828;
  margin: 0 0 0.5rem;
}

.dialog-message {
  font-size: 0.9rem;
  color: #475467;
  margin: 0 0 1.5rem;
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

.btn-secondary,
.btn-primary,
.btn-danger {
  padding: 0.55rem 1.1rem;
  font-size: 0.875rem;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}

.btn-secondary {
  color: #344054;
  background: white;
  border: 1px solid #d0d5dd;
}

.btn-secondary:hover {
  background: #f9fafb;
}

.btn-primary {
  color: white;
  background: #7f56d9;
}

.btn-primary:hover {
  background: #6941c6;
}

.btn-danger {
  color: white;
  background: #d92d20;
}

.btn-danger:hover {
  background: #b42318;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.15s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
