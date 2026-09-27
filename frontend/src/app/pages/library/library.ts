import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { DashboardService, LearningItemsSummary } from '../../core/services/dashboard-service';
import { LearningItemRecencyService } from '../../core/services/learning-item-recency.service';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import { ConfirmationDialog } from '../../shared/components/confirmation-dialog/confirmation-dialog';

interface LibraryItem {
  id: number;
  title: string;
  description: string;
  image: string | null;
  topics: string[];
  images: number;
  pdfs: number;
  createdRecency: string;
  exploredAt: number | null;
}

@Component({
  selector: 'app-library',
  standalone: true,
  imports: [CommonModule, ConfirmationDialog],
  templateUrl: './library.html',
  styleUrl: './library.css',
})
export class Library implements OnInit {
  readonly items = signal<LibraryItem[]>([]);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly searchQuery = signal('');
  readonly topicFilter = signal('');
  readonly failedImageIds = signal<ReadonlySet<number>>(new Set());
  readonly pendingDeleteId = signal<number | null>(null);
  readonly deleting = signal(false);

  readonly topicOptions = computed(() => [...new Set(this.items().flatMap((item) => item.topics))]
    .sort((left, right) => left.localeCompare(right)));
  readonly filteredItems = computed(() => {
    const query = this.searchQuery().trim().toLocaleLowerCase();
    const topic = this.topicFilter();
    return this.items().filter((item) => {
      const matchesQuery = !query
        || item.title.toLocaleLowerCase().includes(query)
        || item.description.toLocaleLowerCase().includes(query)
        || item.topics.some((value) => value.toLocaleLowerCase().includes(query));
      return matchesQuery && (!topic || item.topics.includes(topic));
    });
  });
  readonly pendingDeleteItem = computed(() => {
    const id = this.pendingDeleteId();
    return id === null ? null : this.items().find((item) => item.id === id) ?? null;
  });

  constructor(
    private readonly dashboardService: DashboardService,
    private readonly learningItemService: LearningItem,
    private readonly recencyService: LearningItemRecencyService,
    private readonly toaster: ToasterService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void { this.loadItems(); }

  loadItems(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set(false);
    this.dashboardService.getLearningItemSummary({ localLoading: true })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => this.items.set(response.data.map((item) => this.mapItem(item))),
        error: () => this.error.set(true),
      });
  }

  updateSearch(event: Event): void {
    const target = event.target;
    if (target instanceof HTMLInputElement) this.searchQuery.set(target.value);
  }

  updateTopicFilter(event: Event): void {
    const target = event.target;
    if (target instanceof HTMLSelectElement) this.topicFilter.set(target.value);
  }

  clearFilters(): void {
    this.searchQuery.set('');
    this.topicFilter.set('');
  }

  addMaterial(): void { void this.router.navigate(['/app/new-item']); }
  viewLearningItem(id: number): void { void this.router.navigate(['/app/learning-items', id]); }
  requestDelete(id: number): void { this.pendingDeleteId.set(id); }
  cancelDelete(): void { if (!this.deleting()) this.pendingDeleteId.set(null); }

  confirmDelete(): void {
    const id = this.pendingDeleteId();
    if (id === null || this.deleting()) return;
    this.deleting.set(true);
    this.learningItemService.deleteLearningItem(id)
      .pipe(finalize(() => this.deleting.set(false)))
      .subscribe({
        next: () => {
          this.items.update((items) => items.filter((item) => item.id !== id));
          this.recencyService.remove(id);
          this.pendingDeleteId.set(null);
          this.toaster.success('Learning item deleted.', { title: 'Material removed' });
        },
        error: () => this.toaster.error('The learning item could not be deleted.', { title: 'Delete failed' }),
      });
  }

  imageFailed(id: number): void { this.failedImageIds.update((ids) => new Set(ids).add(id)); }
  hasUsableImage(item: LibraryItem): boolean { return Boolean(item.image) && !this.failedImageIds().has(item.id); }

  itemRecency(item: LibraryItem): string {
    if (item.exploredAt === null) return item.createdRecency;
    const hours = Math.max(0, Math.floor((Date.now() - item.exploredAt) / 3_600_000));
    if (hours === 0) return 'Explored just now';
    if (hours < 24) return `Explored ${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `Explored ${days} ${days === 1 ? 'day' : 'days'} ago`;
  }

  private mapItem(item: LearningItemsSummary): LibraryItem {
    const description = this.stripHtml(item.description_text ?? '').trim();
    return {
      id: item.id,
      title: item.title,
      description: description || 'No notes preview is available for this learning item.',
      image: item.first_image_url,
      topics: item.labels?.split(',').map((label) => label.trim()).filter(Boolean) ?? [],
      images: item.image_count,
      pdfs: item.pdf_count,
      createdRecency: this.formatHoursAgo(item.hours_ago),
      exploredAt: this.recencyService.exploredAt(item.id),
    };
  }

  private formatHoursAgo(hours: number): string {
    if (hours <= 0) return 'Created just now';
    if (hours < 24) return `Created ${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `Created ${days} ${days === 1 ? 'day' : 'days'} ago`;
  }

  private stripHtml(html: string): string {
    const container = document.createElement('div');
    container.innerHTML = html;
    return container.textContent ?? '';
  }
}
