import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastOptions {
  title?: string;
  duration?: number;
  dismissible?: boolean;
}

export interface Toast {
  id: number;
  type: ToastType;
  message: string;
  title?: string;
  duration: number;
  dismissible: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class ToasterService {
  private readonly defaultDuration = 4000;
  private readonly activeToasts = signal<Toast[]>([]);
  private readonly timers = new Map<number, ReturnType<typeof setTimeout>>();

  readonly toasts = this.activeToasts.asReadonly();

  private nextId = 1;

  show(
    type: ToastType,
    message: string,
    options: ToastOptions = {}
  ): number {
    const toast: Toast = {
      id: this.nextId++,
      type,
      message,
      title: options.title,
      duration: options.duration ?? this.defaultDuration,
      dismissible: options.dismissible ?? true,
    };

    this.activeToasts.update((toasts) => [
      toast,
      ...toasts,
    ]);

    if (toast.duration > 0) {
      const timer = setTimeout(() => {
        this.remove(toast.id);
      }, toast.duration);

      this.timers.set(toast.id, timer);
    }

    return toast.id;
  }

  success(message: string, options?: ToastOptions): number {
    return this.show('success', message, options);
  }

  error(message: string, options?: ToastOptions): number {
    return this.show('error', message, options);
  }

  warning(message: string, options?: ToastOptions): number {
    return this.show('warning', message, options);
  }

  info(message: string, options?: ToastOptions): number {
    return this.show('info', message, options);
  }

  remove(id: number): void {
    const timer = this.timers.get(id);

    if (timer) {
      clearTimeout(timer);
      this.timers.delete(id);
    }

    this.activeToasts.update((toasts) =>
      toasts.filter((toast) => toast.id !== id)
    );
  }

  clear(): void {
    this.timers.forEach((timer) => {
      clearTimeout(timer);
    });

    this.timers.clear();
    this.activeToasts.set([]);
  }
}
