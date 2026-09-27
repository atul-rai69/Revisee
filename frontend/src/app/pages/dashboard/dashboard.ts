import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';
import { DashboardService, LearningItemsSummary } from '../../core/services/dashboard-service';
import { LearningItemRecencyService } from '../../core/services/learning-item-recency.service';
import { MasteryAnalyticsItem, MasteryService } from '../../core/services/mastery.service';

interface DashboardItem {
  id: number;
  title: string;
  description: string;
  image: string | null;
  topics: string[];
  images: number;
  pdfs: number;
  createdHoursAgo: number;
  createdRecency: string;
  exploredAt: number | null;
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
  readonly itemsLoading = signal(false);
  readonly itemsError = signal(false);
  readonly masteryLoading = signal(false);
  readonly masteryError = signal(false);
  readonly failedImageIds = signal<ReadonlySet<number>>(new Set());
  readonly items = signal<DashboardItem[]>([]);
  readonly masteryItems = signal<MasteryAnalyticsItem[]>([]);

  readonly exploredItems = computed(() => this.items()
    .filter((item) => item.exploredAt !== null)
    .sort((left, right) => (right.exploredAt ?? 0) - (left.exploredAt ?? 0)));
  readonly hasExplorationHistory = computed(() => this.exploredItems().length > 0);
  readonly visibleItems = computed(() => {
    if (this.hasExplorationHistory()) return this.exploredItems().slice(0, 4);
    return [...this.items()].sort((left, right) => left.createdHoursAgo - right.createdHoursAgo).slice(0, 4);
  });

  constructor(
    private readonly dashboardService: DashboardService,
    private readonly masteryService: MasteryService,
    private readonly recencyService: LearningItemRecencyService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.loadSummary();
    this.loadItems();
    this.loadMasterySummary();
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

  loadMasterySummary(): void {
    if (this.masteryLoading()) return;
    this.masteryLoading.set(true);
    this.masteryError.set(false);
    forkJoin([
      this.masteryService.getAnalytics('LABEL', 2),
      this.masteryService.getAnalytics('LEARNING_ITEM', 2),
    ]).pipe(finalize(() => this.masteryLoading.set(false))).subscribe({
      next: ([topics, items]) => this.masteryItems.set([...topics.items, ...items.items]),
      error: () => this.masteryError.set(true),
    });
  }

  masteryStatus(item: MasteryAnalyticsItem): string {
    return ({
      NO_QUESTIONS: 'No questions',
      NOT_ATTEMPTED: 'Not attempted',
      INSUFFICIENT_EVIDENCE: 'Building evidence',
      MEASURED: `${item.mastery_score}% mastery`,
    })[item.evidence_status];
  }

  itemRecency(item: DashboardItem): string {
    if (item.exploredAt === null) return item.createdRecency;
    const elapsedHours = Math.max(0, Math.floor((Date.now() - item.exploredAt) / 3_600_000));
    if (elapsedHours === 0) return 'Explored just now';
    if (elapsedHours < 24) return `Explored ${elapsedHours}h ago`;
    const days = Math.floor(elapsedHours / 24);
    return `Explored ${days} ${days === 1 ? 'day' : 'days'} ago`;
  }

  startRevision(strategy: 'RANDOM' | 'LABEL'): void {
    void this.router.navigate(['/app/revise'], { queryParams: { strategy } });
  }

  addMaterial(): void { void this.router.navigate(['/app/new-item']); }
  viewLibrary(): void { void this.router.navigate(['/app/library']); }
  viewAnalytics(): void { void this.router.navigate(['/app/analytics']); }
  viewLearningItem(id: number): void { void this.router.navigate(['/app/learning-items', id]); }

  imageFailed(id: number): void {
    this.failedImageIds.update((ids) => new Set(ids).add(id));
  }

  hasUsableImage(item: DashboardItem): boolean {
    return Boolean(item.image) && !this.failedImageIds().has(item.id);
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
      createdHoursAgo: item.hours_ago,
      createdRecency: this.formatHoursAgo(item.hours_ago),
      exploredAt: this.recencyService.exploredAt(item.id),
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
