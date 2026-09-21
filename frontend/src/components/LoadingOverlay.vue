<script setup lang="ts">
import { useLoadingStore } from "@/stores/loading";

const loading = useLoadingStore();
</script>

<template>
  <div v-if="loading.isLoading" class="loading-overlay" role="status" aria-label="Memuat…">
    <div class="dots">
      <span class="dot" />
      <span class="dot" />
      <span class="dot" />
    </div>
  </div>
</template>

<style scoped>
/* Fixed + full viewport + sits above everything, so it also physically
   blocks pointer events on whatever is underneath — this is what stops
   spam-clicking a button while its request is still in flight, not just
   the visual "something is happening" feedback. */
.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(1px);
}

.dots {
  display: flex;
  gap: 0.5rem;
}

.dot {
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  background: #7f56d9;
  animation: bounce 1.1s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.24s;
}

.dot:nth-child(2) {
  animation-delay: -0.12s;
}

.dot:nth-child(3) {
  animation-delay: 0s;
}

@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
