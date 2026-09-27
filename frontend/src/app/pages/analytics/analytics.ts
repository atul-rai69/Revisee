import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import type { EChartsCoreOption } from 'echarts/core';
import { finalize, forkJoin } from 'rxjs';
import {
  MasteryAnalyticsItem,
  MasteryEntityType,
  MasteryService,
  RevisionAnalyticsResponse,
  WeakAreaItem,
} from '../../core/services/mastery.service';
import {
  illustrativeWeakAreaOption,
  individualMasteryOption,
  masteryGrowthOption,
  revisionActivityOption,
  topicPracticeBubbleOption,
  weakAreaOption,
} from '../../shared/charts/revisee-chart-options';
import { EChart } from '../../shared/components/echart/echart';

@Component({
  selector: 'app-analytics',
  imports: [CommonModule, EChart],
  templateUrl: './analytics.html',
  styleUrls: ['./analytics.css', './analytics-overview.css'],
})
export class Analytics implements OnInit {
  readonly entityType = signal<MasteryEntityType>('LABEL');
  readonly items = signal<MasteryAnalyticsItem[]>([]);
  readonly total = signal(0);
  readonly minimumAttempts = signal(3);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly expandedIds = signal<ReadonlySet<number>>(new Set());
  readonly limit = 20;
  readonly distributionLimits = [7, 30, 50] as const;
  readonly pageEnd = computed(() => Math.min(this.offset() + this.limit, this.total()));

  readonly revisionAnalytics = signal<RevisionAnalyticsResponse | null>(null);
  readonly topicAnalytics = signal<MasteryAnalyticsItem[]>([]);
  readonly topicMinimumAttempts = signal(3);
  readonly selectedTopicIds = signal<ReadonlySet<number>>(new Set());
  readonly distributionLimit = signal<7 | 30 | 50>(30);
  readonly insightsLoading = signal(false);
  readonly insightsError = signal(false);
  readonly weakAreas = signal<WeakAreaItem[]>([]);
  readonly weakLoading = signal(false);
  readonly weakError = signal(false);
  readonly reducedMotion = typeof matchMedia === 'function'
    && matchMedia('(prefers-reduced-motion: reduce)').matches;
  readonly selectedTopicAnalytics = computed(() => this.topicAnalytics().filter(
    (item) => this.selectedTopicIds().has(item.entity_id),
  ));
  readonly activityOption = computed<EChartsCoreOption | null>(() => {
    const points = this.revisionAnalytics()?.activity ?? [];
    return points.length ? revisionActivityOption(points, this.reducedMotion) : null;
  });
  readonly topicGrowthOption = computed<EChartsCoreOption | null>(() => {
    const items = this.selectedTopicAnalytics();
    return items.length ? masteryGrowthOption(items, this.topicMinimumAttempts(), this.reducedMotion) : null;
  });
  readonly bubbleOption = computed<EChartsCoreOption | null>(() => {
    const points = this.revisionAnalytics()?.topic_practice ?? [];
    return points.length ? topicPracticeBubbleOption(points, this.reducedMotion) : null;
  });
  readonly weakChartOption = computed<EChartsCoreOption>(() => {
    const items = this.weakAreas();
    return items.length
      ? weakAreaOption(items, this.reducedMotion)
      : illustrativeWeakAreaOption(this.reducedMotion);
  });

  constructor(private readonly service: MasteryService, private readonly router: Router) {}

  ngOnInit(): void {
    this.load();
    this.loadInsights();
  }

  load(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.error.set(false);
    this.service.getAnalytics(this.entityType(), this.limit, this.offset())
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.items.set(response.items);
          this.total.set(response.total);
          this.minimumAttempts.set(response.minimum_attempts);
          this.expandedIds.set(new Set());
        },
        error: () => this.error.set(true),
      });
  }

  loadInsights(): void {
    if (this.insightsLoading()) return;
    this.insightsLoading.set(true);
    this.insightsError.set(false);
    forkJoin([
      this.service.getRevisionAnalytics(this.distributionLimit()),
      this.service.getAnalytics('LABEL', 100),
    ])
      .pipe(finalize(() => this.insightsLoading.set(false)))
      .subscribe({
        next: ([response, topics]) => {
          this.revisionAnalytics.set(response);
          this.topicAnalytics.set(topics.items);
          this.topicMinimumAttempts.set(topics.minimum_attempts);
          const availableIds = new Set(topics.items.map((item) => item.entity_id));
          const retained = [...this.selectedTopicIds()].filter((id) => availableIds.has(id));
          const defaults = topics.items
            .filter((item) => this.hasMeasuredTopicTrend(item))
            .slice(0, 3)
            .map((item) => item.entity_id);
          this.selectedTopicIds.set(new Set(retained.length ? retained : defaults));
          if (response.weak_area_ready) this.loadWeakAreas();
          else {
            this.weakAreas.set([]);
            this.weakError.set(false);
          }
        },
        error: () => this.insightsError.set(true),
      });
  }

  loadWeakAreas(): void {
    if (this.weakLoading()) return;
    this.weakLoading.set(true);
    this.weakError.set(false);
    forkJoin([
      this.service.getWeakAreas('DEMONSTRATED_WEAKNESS'),
      this.service.getWeakAreas('DUE_REVIEW'),
    ])
      .pipe(finalize(() => this.weakLoading.set(false)))
      .subscribe({
        next: ([weak, due]) => this.weakAreas.set([...weak.items, ...due.items]),
        error: () => this.weakError.set(true),
      });
  }

  selectDistributionLimit(limit: 7 | 30 | 50): void {
    if (limit === this.distributionLimit()) return;
    this.distributionLimit.set(limit);
    this.loadInsights();
  }

  toggleGrowthTopic(topicId: number): void {
    this.selectedTopicIds.update((selected) => {
      const next = new Set(selected);
      if (next.has(topicId)) next.delete(topicId);
      else if (next.size < 5) next.add(topicId);
      return next;
    });
  }

  hasMeasuredTopicTrend(item: MasteryAnalyticsItem): boolean {
    return item.evidence_status === 'MEASURED'
      && item.trend.some((point) => point.total_attempts >= this.topicMinimumAttempts());
  }

  formatActivityDate(value: string): string {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
  }

  selectType(type: MasteryEntityType): void {
    if (type === this.entityType()) return;
    this.entityType.set(type);
    this.offset.set(0);
    this.load();
  }

  previous(): void {
    this.offset.update((value) => Math.max(0, value - this.limit));
    this.load();
  }

  next(): void {
    if (this.offset() + this.limit < this.total()) {
      this.offset.update((value) => value + this.limit);
      this.load();
    }
  }

  toggleTrend(entityId: number): void {
    this.expandedIds.update((expanded) => {
      const next = new Set(expanded);
      if (next.has(entityId)) next.delete(entityId);
      else next.add(entityId);
      return next;
    });
  }

  statusLabel(item: MasteryAnalyticsItem): string {
    return ({
      NO_QUESTIONS: 'No questions',
      NOT_ATTEMPTED: 'Mastery locked',
      INSUFFICIENT_EVIDENCE: 'Practise more to unlock mastery',
      MEASURED: 'Measured',
    })[item.evidence_status];
  }

  evidenceGuidance(item: MasteryAnalyticsItem): string {
    if (item.evidence_status === 'NO_QUESTIONS') return 'Add questions before mastery evidence can be collected.';
    if (item.evidence_status === 'MEASURED') return 'This mastery score is supported by persisted revision attempts.';
    return 'Practise questions from this Topic/item to reveal your mastery.';
  }

  remainingAttempts(item: MasteryAnalyticsItem): number {
    return Math.max(0, this.minimumAttempts() - item.total_attempts);
  }

  actionLabel(item: MasteryAnalyticsItem): string {
    if (item.question_count === 0) return 'Add questions';
    return item.total_attempts === 0 ? 'Start practice' : 'Practise again';
  }

  openAction(item: MasteryAnalyticsItem): void {
    if (item.question_count === 0) {
      const destination = this.entityType() === 'LEARNING_ITEM'
        ? ['/app/learning-items', item.entity_id, 'questions']
        : ['/app/new-item'];
      void this.router.navigate(destination);
      return;
    }
    void this.router.navigate(
      ['/app/revise'],
      this.entityType() === 'LABEL' ? { queryParams: { strategy: 'LABEL' } } : undefined,
    );
  }

  individualOption(item: MasteryAnalyticsItem): EChartsCoreOption {
    return individualMasteryOption(item, this.minimumAttempts(), this.reducedMotion);
  }

  measuredTrendCount(item: MasteryAnalyticsItem): number {
    return item.trend.filter((point) => point.total_attempts >= this.minimumAttempts()).length;
  }

  formatDate(value: string | null): string {
    return value
      ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
      : 'Not available';
  }
}
