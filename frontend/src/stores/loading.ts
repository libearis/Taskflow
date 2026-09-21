import { defineStore } from "pinia";

// Counter-based, not a boolean: if two BE-dependent actions overlap (rare,
// but e.g. delete + a still-settling status change), the overlay must stay
// up until BOTH finish, not disappear when the first one does.
export const useLoadingStore = defineStore("loading", {
  state: () => ({
    activeCount: 0,
  }),

  getters: {
    isLoading: (state) => state.activeCount > 0,
  },

  actions: {
    start() {
      this.activeCount++;
    },
    stop() {
      this.activeCount = Math.max(0, this.activeCount - 1);
    },
    async wrap<T>(fn: () => Promise<T>): Promise<T> {
      this.start();
      try {
        return await fn();
      } finally {
        this.stop();
      }
    },
  },
});
