import { defineStore } from "pinia";

interface ConfirmOptions {
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface AlertOptions {
  title?: string;
  okLabel?: string;
  danger?: boolean;
}

// Promise-based replacement for window.confirm()/alert() — a proper modal
// instead of the browser's native dialog, which we also can't style, and
// which some automated/embedded browser contexts silently suppress.
export const useConfirmStore = defineStore("confirm", {
  state: () => ({
    visible: false,
    mode: "confirm" as "confirm" | "alert",
    title: "",
    message: "",
    confirmLabel: "Konfirmasi",
    cancelLabel: "Batal",
    danger: false,
    resolver: null as ((value: boolean) => void) | null,
  }),

  actions: {
    confirm(message: string, opts: ConfirmOptions = {}): Promise<boolean> {
      this.mode = "confirm";
      this.title = opts.title ?? "Konfirmasi";
      this.message = message;
      this.confirmLabel = opts.confirmLabel ?? "Konfirmasi";
      this.cancelLabel = opts.cancelLabel ?? "Batal";
      this.danger = opts.danger ?? false;
      this.visible = true;
      return new Promise((resolve) => {
        this.resolver = resolve;
      });
    },

    alert(message: string, opts: AlertOptions = {}): Promise<void> {
      this.mode = "alert";
      this.title = opts.title ?? "Pemberitahuan";
      this.message = message;
      this.confirmLabel = opts.okLabel ?? "OK";
      this.danger = opts.danger ?? false;
      this.visible = true;
      return new Promise((resolve) => {
        this.resolver = () => resolve();
      });
    },

    respond(value: boolean) {
      this.visible = false;
      this.resolver?.(value);
      this.resolver = null;
    },
  },
});
