import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { EChartsCoreOption } from 'echarts/core';
import { finalize, forkJoin } from 'rxjs';
import { RevisionHistoryItem } from '../../core/models/revision.models';
import {
  MasteryAnalyticsItem,
  MasteryService,
  RevisionAnalyticsResponse,
} from '../../core/services/mastery.service';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import {
  DashboardService,
  LearningItemsSummary,
} from '../../core/services/dashboard-service';
import { Label, LabelService } from '../../core/services/label-service';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import { AICredential, AICredentialsService } from '../../core/services/ai-credentials.service';
import { EChart } from '../../shared/components/echart/echart';
import {
  masteryGrowthOption,
  revisionActivityOption,
} from '../../shared/charts/revisee-chart-options';

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
  imports: [CommonModule, EChart],
  templateUrl: './dashboard.html',
  styleUrls: ['./dashboard.css', './dashboard-content.css', './dashboard-analytics.css'],
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
  readonly recentRevisions = signal<RevisionHistoryItem[]>([]);
  readonly revisionsLoading = signal(false);
  readonly revisionsError = signal(false);
  readonly masteryItems = signal<MasteryAnalyticsItem[]>([]);
  readonly masteryLoading = signal(false);
  readonly masteryError = signal(false);
  readonly analysis = signal<RevisionAnalyticsResponse | null>(null);
  readonly topicAnalytics = signal<MasteryAnalyticsItem[]>([]);
  readonly topicMinimumAttempts = signal(3);
  readonly analysisLoading = signal(false);
  readonly analysisError = signal(false);
  readonly aiCredentials = signal<AICredential[]>([]);
  readonly aiCredentialsLoading = signal(false);
  readonly aiCredentialsError = signal(false);
  readonly selectedTopicIds = signal<ReadonlySet<number>>(new Set());
  readonly reducedMotion = typeof matchMedia === 'function'
    && matchMedia('(prefers-reduced-motion: reduce)').matches;

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
  readonly selectedTopicAnalytics = computed(() => this.topicAnalytics().filter(
    (item) => this.selectedTopicIds().has(item.entity_id),
  ));
  readonly activityChartOption = computed<EChartsCoreOption | null>(() => {
    const activity = this.analysis()?.activity ?? [];
    return activity.length ? revisionActivityOption(activity, this.reducedMotion) : null;
  });
  readonly topicGrowthChartOption = computed<EChartsCoreOption | null>(() => {
    const items = this.selectedTopicAnalytics();
    return items.length
      ? masteryGrowthOption(items, this.topicMinimumAttempts(), this.reducedMotion)
      : null;
  });

  constructor(
    private readonly dashboardService: DashboardService,
    private readonly labelService: LabelService,
    private readonly router: Router,
    private readonly learningItemService: LearningItem,
    private readonly toaster: ToasterService,
    private readonly revisionService: RevisionSessionService,
    private readonly masteryService: MasteryService,
    private readonly aiCredentialService: AICredentialsService,
  ) {}

  ngOnInit(): void {
    this.loadSummary();
    this.loadTopics();
    this.loadItems();
    this.loadRecentRevisions();
    this.loadMasterySummary();
    this.loadAnalysis();
    this.loadAICredentials();
  }

  loadAICredentials(): void {
    if (this.aiCredentialsLoading()) return;
    this.aiCredentialsLoading.set(true);
    this.aiCredentialsError.set(false);
    this.aiCredentialService.list().pipe(finalize(() => this.aiCredentialsLoading.set(false))).subscribe({
      next: (response) => this.aiCredentials.set(response.credentials),
      error: () => this.aiCredentialsError.set(true),
    });
  }

  defaultAICredential(): AICredential | null {
    return this.aiCredentials().find((credential) => credential.is_default) ?? null;
  }

  manageAICredentials(): void { void this.router.navigate(['/app/settings']); }

  loadAnalysis(): void {
    if (this.analysisLoading()) return;
    this.analysisLoading.set(true);
    this.analysisError.set(false);
    forkJoin([
      this.masteryService.getRevisionAnalytics(30),
      this.masteryService.getAnalytics('LABEL', 100),
    ]).pipe(finalize(() => this.analysisLoading.set(false))).subscribe({
      next: ([analysis, topics]) => {
        this.analysis.set(analysis);
        this.topicAnalytics.set(topics.items);
        this.topicMinimumAttempts.set(topics.minimum_attempts);
        const defaults = topics.items
          .filter((item) => item.evidence_status === 'MEASURED'
            && item.trend.some((point) => point.total_attempts >= topics.minimum_attempts))
          .slice(0, 3)
          .map((item) => item.entity_id);
        this.selectedTopicIds.set(new Set(defaults));
      },
      error: () => this.analysisError.set(true),
    });
  }

  toggleGrowthTopic(topicId: number): void {
    this.selectedTopicIds.update((selected) => {
      const next = new Set(selected);
      if (next.has(topicId)) next.delete(topicId);
      else if (next.size < 5) next.add(topicId);
      return next;
    });
  }

  hasMeasuredTrend(item: MasteryAnalyticsItem): boolean {
    return item.evidence_status === 'MEASURED'
      && item.trend.some((point) => point.total_attempts >= this.topicMinimumAttempts());
  }

  formatActivityDate(value: string): string {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
  }

  loadRecentRevisions(): void {
    if (this.revisionsLoading()) return;
    this.revisionsLoading.set(true); this.revisionsError.set(false);
    this.revisionService.getHistory({ limit: 4 })
      .pipe(finalize(() => this.revisionsLoading.set(false)))
      .subscribe({ next: (page) => this.recentRevisions.set(page.items), error: () => this.revisionsError.set(true) });
  }

  loadMasterySummary(): void {
    if (this.masteryLoading()) return;
    this.masteryLoading.set(true); this.masteryError.set(false);
    forkJoin([
      this.masteryService.getAnalytics('LABEL', 2),
      this.masteryService.getAnalytics('LEARNING_ITEM', 2),
    ]).pipe(finalize(() => this.masteryLoading.set(false))).subscribe({
      next: ([topics, items]) => this.masteryItems.set([...topics.items, ...items.items]),
      error: () => this.masteryError.set(true),
    });
  }

  openRevision(session: RevisionHistoryItem): void {
    const suffix = session.status === 'COMPLETED' ? ['result'] : [];
    void this.router.navigate(['/app/revision-sessions', session.session_id, ...suffix]);
  }

  viewRevisionHistory(): void { void this.router.navigate(['/app/revision-sessions']); }
  viewAnalytics(): void { void this.router.navigate(['/app/analytics']); }
  masteryStatus(item: MasteryAnalyticsItem): string {
    return ({ NO_QUESTIONS: 'No questions', NOT_ATTEMPTED: 'Not attempted', INSUFFICIENT_EVIDENCE: 'Building evidence', MEASURED: `${item.mastery_score}% mastery` })[item.evidence_status];
  }
  strategyLabel(strategy: string): string { return ({ RANDOM: 'Quick', LABEL: 'Topic', SMART: 'SMART' } as Record<string, string>)[strategy] ?? strategy; }
  formatRevisionDate(value: string | null): string { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : 'Date unavailable'; }

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
