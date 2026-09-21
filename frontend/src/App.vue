<script setup lang="ts">
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <router-link to="/" class="brand">
        <span class="brand-mark">T</span>
        <h1>TaskFlow</h1>
      </router-link>
    </header>
    <main>
      <router-view />
    </main>
    <LoadingOverlay />
    <ConfirmDialog />
  </div>
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  background: #f4f5f7;
  color: #101828;
  -webkit-font-smoothing: antialiased;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.1rem 2rem;
  background: #101828;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  text-decoration: none;
  color: white;
  padding: 0.3rem 0.8rem;
  border-radius: 10px;
  transition: background 0.15s;
}

.brand:hover {
  background: rgba(255, 255, 255, 0.08);
}

.brand-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 9px;
  background: #7f56d9;
  color: white;
  font-size: 1.2rem;
  font-weight: 800;
}

.app-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}

.app-shell main {
  padding: 2rem 1.5rem;
}
</style>
