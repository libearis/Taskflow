<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getUserWorkload, type UserWorkload } from "@/api/rest";

const props = defineProps<{ userId: string }>();

const workload = ref<UserWorkload | null>(null);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    workload.value = await getUserWorkload(props.userId);
  } catch {
    error.value = "Workload belum tersedia — mungkin belum ter-sync dari outbox.";
  }
});
</script>

<template>
  <section>
    <h2>Workload</h2>
    <p v-if="error">{{ error }}</p>
    <div v-else-if="workload">
      <p>Active tasks: {{ workload.active_tasks }}</p>
      <ul>
        <li v-for="p in workload.tasks_by_project" :key="p.project_id">
          {{ p.project_name }}: {{ p.count }}
        </li>
      </ul>
    </div>
  </section>
</template>
