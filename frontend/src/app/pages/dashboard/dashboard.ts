import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import {
  DashboardService,
  LearningItemsSummary,
} from '../../core/services/dashboard-service';
import { Label, LabelService } from '../../core/services/label-service';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';

interface DashboardItem {
  id: number;
  title: string;
  description: string;
  image: string | null;
  topics: string[];
  images: number;
  pdfs: number;
  recency: string;
}

export function greetingForHour(hour: number): 'Good morning' | 'Good afternoon' | 'Good evening' {
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css', './dashboard-content.css'],
})
export class Dashboard implements OnInit {
  readonly username = signal('');
  readonly totalItems = signal(0);
  readonly totalTopics = signal(0);
  readonly activeDays = signal(0);
  readonly greeting = greetingForHour(new Date().getHours());

  readonly summaryLoading = signal(false);
  readonly summaryError = signal(false);
  readonly topicsLoading = signal(false);
  readonly topicsError = signal(false);
  readonly itemsLoading = signal(false);
  readonly itemsError = signal(false);
  readonly deletingIds = signal<ReadonlySet<number>>(new Set());
  readonly failedImageIds = signal<ReadonlySet<number>>(new Set());
  readonly topics = signal<Label[]>([]);
  readonly items = signal<DashboardItem[]>([]);
  readonly searchQuery = signal('');

  readonly visibleTopics = computed(() => this.topics().slice(0, 6));
  readonly filteredItems = computed(() => {
    const query = this.searchQuery().trim().toLocaleLowerCase();
    if (!query) return this.items();
    return this.items().filter((item) =>
      item.title.toLocaleLowerCase().includes(query)
      || item.description.toLocaleLowerCase().includes(query)
      || item.topics.some((topic) => topic.toLocaleLowerCase().includes(query)),
    );
  });

  constructor(
    private readonly dashboardService: DashboardService,
    private readonly labelService: LabelService,
    private readonly router: Router,
    private readonly learningItemService: LearningItem,
    private readonly toaster: ToasterService,
  ) {}

  ngOnInit(): void {
    this.loadSummary();
    this.loadTopics();
    this.loadItems();
  }

  loadSummary(): void {
    if (this.summaryLoading()) return;
    this.summaryLoading.set(true);
    this.summaryError.set(false);
    this.dashboardService.getDashboardSummary({ localLoading: true })
      .pipe(finalize(() => this.summaryLoading.set(false)))
      .subscribe({
        next: (data) => {
          this.username.set(data.username);
          this.totalItems.set(data.total_items);
          this.totalTopics.set(data.total_labels);
          this.activeDays.set(data.login_streak);
        },
        error: () => this.summaryError.set(true),
      });
  }

  loadTopics(): void {
    if (this.topicsLoading()) return;
    this.topicsLoading.set(true);
    this.topicsError.set(false);
    this.labelService.getLabels({ localLoading: true })
      .pipe(finalize(() => this.topicsLoading.set(false)))
      .subscribe({
        next: (topics) => this.topics.set(topics),
        error: () => this.topicsError.set(true),
      });
  }

  loadItems(): void {
    if (this.itemsLoading()) return;
    this.itemsLoading.set(true);
    this.itemsError.set(false);
    this.dashboardService.getLearningItemSummary({ localLoading: true })
      .pipe(finalize(() => this.itemsLoading.set(false)))
      .subscribe({
        next: (response) => this.items.set(response.data.map((item) => this.mapItem(item))),
        error: () => this.itemsError.set(true),
      });
  }

  updateSearch(event: Event): void {
    const target = event.target;
    if (target instanceof HTMLInputElement) this.searchQuery.set(target.value);
  }

  topicInitials(topic: Label): string {
    return topic.label_name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0]?.toLocaleUpperCase() ?? '')
      .join('') || 'T';
  }

  topicTone(topic: Label): string {
    return ['purple', 'green', 'orange', 'coral'][Math.abs(topic.id) % 4];
  }

  startRevision(strategy: 'RANDOM' | 'LABEL'): void {
    void this.router.navigate(['/app/revise'], { queryParams: { strategy } });
  }

  viewTopics(): void {
    void this.router.navigate(['/app/labels']);
  }

  addMaterial(): void {
    void this.router.navigate(['/app/new-item']);
  }

  viewLearningItem(id: number): void {
    void this.router.navigate(['/app/learning-items', id]);
  }

  imageFailed(id: number): void {
    this.failedImageIds.update((ids) => new Set(ids).add(id));
  }

  hasUsableImage(item: DashboardItem): boolean {
    return Boolean(item.image) && !this.failedImageIds().has(item.id);
  }

  deleteItem(event: Event, id: number): void {
    event.stopPropagation();
    if (this.deletingIds().has(id)) return;
    this.deletingIds.update((ids) => new Set(ids).add(id));
    this.learningItemService.deleteLearningItem(id)
      .pipe(finalize(() => this.deletingIds.update((ids) => {
        const next = new Set(ids);
        next.delete(id);
        return next;
      })))
      .subscribe({
        next: () => {
          this.items.update((items) => items.filter((item) => item.id !== id));
          this.totalItems.update((count) => Math.max(0, count - 1));
          this.toaster.success('Learning item deleted.', { title: 'Material removed' });
        },
        error: () => this.toaster.error('The learning item could not be deleted.', { title: 'Delete failed' }),
      });
  }

  private mapItem(item: LearningItemsSummary): DashboardItem {
    const description = this.stripHtml(item.description_text ?? '').trim();
    return {
      id: item.id,
      title: item.title,
      description: description || 'No notes preview is available for this learning item.',
      image: item.first_image_url,
      topics: this.parseTopics(item.labels),
      images: item.image_count,
      pdfs: item.pdf_count,
      recency: this.formatHoursAgo(item.hours_ago),
    };
  }

  private parseTopics(labels: string | null): string[] {
    return labels ? labels.split(',').map((label) => label.trim()).filter(Boolean) : [];
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
