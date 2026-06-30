import { Injectable, computed, signal } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class LoaderService {
  private readonly activeRequests = signal(0);

  readonly isLoading = computed(() => this.activeRequests() > 0);

  show(): void {
    this.activeRequests.update((count) => count + 1);
  }

  hide(): void {
    this.activeRequests.update((count) => Math.max(count - 1, 0));
  }

  reset(): void {
    this.activeRequests.set(0);
  }
}
