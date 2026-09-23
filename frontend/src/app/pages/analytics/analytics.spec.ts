import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import {
  MasteryService,
  RevisionAnalyticsResponse,
} from '../../core/services/mastery.service';
import { EChartsLoaderService } from '../../shared/components/echart/echarts-loader.service';
import { Analytics } from './analytics';

class FakeMasteryService {
  revisionCalls = 0;
  revisionResult: Observable<RevisionAnalyticsResponse> = of({
    completed_session_count: 0,
    activity: [],
    requested_session_limit: 30,
    sessions_used: 0,
    measured_learning_item_count: 0,
    weak_area_ready: false,
    minimum_attempts: 3,
    topic_attribution: 'CURRENT_LEARNING_ITEM_TOPICS',
    attribution_note: 'Topic totals can overlap.',
    topic_practice: [],
  });
  getAnalytics(entityType: 'LABEL' | 'LEARNING_ITEM') {
    return of({ entity_type: entityType, minimum_attempts: 3, offset: 0, limit: 20, total: 3, items: [
      { entity_id: 1, display_name: 'Unattempted', question_count: 2, evidence_status: 'NOT_ATTEMPTED' as const, mastery_score: null, total_attempts: 0, correct_attempts: 0, accuracy_percent: null, last_practised_at: null, next_review_at: null, trend: [] },
      { entity_id: 2, display_name: 'Measured', question_count: 4, evidence_status: 'MEASURED' as const, mastery_score: 72, total_attempts: 5, correct_attempts: 4, accuracy_percent: 80, last_practised_at: '2026-09-14T10:00:00Z', next_review_at: null, trend: [{ session_id: 1, recorded_at: '2026-09-14T10:00:00Z', score_before: 50, score_after: 72, total_attempts: 5, correct_attempts: 4 }] },
      { entity_id: 3, display_name: 'Building evidence', question_count: 2, evidence_status: 'INSUFFICIENT_EVIDENCE' as const, mastery_score: null, total_attempts: 1, correct_attempts: 1, accuracy_percent: 100, last_practised_at: '2026-09-14T10:00:00Z', next_review_at: null, trend: [{ session_id: 2, recorded_at: '2026-09-14T10:00:00Z', score_before: 50, score_after: 56, total_attempts: 1, correct_attempts: 1 }] },
    ] });
  }
  getRevisionAnalytics(_sessionLimit: 7 | 30 | 50) {
    this.revisionCalls += 1;
    return this.revisionResult;
  }
  getWeakAreas(_classification: 'DEMONSTRATED_WEAKNESS' | 'DUE_REVIEW') { return of({ items: [], pagination: { offset: 0, limit: 8, total: 0 } }); }
}

class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('Analytics', () => {
  let fixture: ComponentFixture<Analytics>;
  let component: Analytics;

  beforeEach(async () => {
    const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [Analytics],
      providers: [
        { provide: MasteryService, useClass: FakeMasteryService },
        { provide: Router, useClass: FakeRouter },
        { provide: EChartsLoaderService, useValue: { load: () => Promise.resolve({ init: () => chart }) } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Analytics);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('renders locked, insufficient, and measured states without exposing default mastery', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Mastery locked');
    expect(text).toContain('Practise more to unlock mastery');
    expect(text).toContain('2 more persisted attempts');
    expect(text).toContain('72%');
    expect(text).not.toContain('56%');
    expect(text).not.toContain('50%');
  });

  it('shows a real one-point history without creating another point', async () => {
    component.toggleTrend(2);
    fixture.detectChanges();
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('1 measured snapshot');
    expect(text).toContain('Session 1');
    expect(text).toContain('72% mastery');
  });

  it('keeps illustrative weak-area data explicitly separate from personal results', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Locked — illustrative preview');
    expect(text).toContain('Example data—not your results.');
    expect(text).toContain('never included in your analytics calculations');
  });

  it('distinguishes measured current mastery from missing historical trend data', () => {
    component.items.set([{
      entity_id: 9, display_name: 'Legacy measured item', question_count: 4,
      evidence_status: 'MEASURED', mastery_score: 68, total_attempts: 4,
      correct_attempts: 3, accuracy_percent: 75, last_practised_at: null,
      next_review_at: null, trend: [],
    }]);
    component.toggleTrend(9);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Current mastery is measured, but no eligible historical snapshots exist yet.',
    );
  });

  it('replaces illustrative content when authoritative readiness permits real results', () => {
    component.revisionAnalytics.update((value) => value ? { ...value, weak_area_ready: true } : value);
    component.weakAreas.set([{
      entity_id: 4, display_name: 'Relational joins', mastery_score: 44,
      total_attempts: 6, correct_attempts: 2, accuracy_percent: 33.33,
      classification: 'DEMONSTRATED_WEAKNESS',
      reason: 'Mastery is below the threshold.',
    }]);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Relational joins');
    expect(text).not.toContain('Example data—not your results.');
  });

  it('shows a retry action when chart aggregation fails', () => {
    component.insightsError.set(true);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Topic practice analysis could not be loaded.');
    expect(text).toContain('Retry');
  });

  it('stops failed insight loading without an automatic retry loop', () => {
    const service = TestBed.inject(MasteryService) as unknown as FakeMasteryService;
    service.revisionResult = throwError(() => new Error('contract failure'));

    component.loadInsights();
    fixture.detectChanges();
    expect(component.insightsLoading()).toBe(false);
    expect(component.insightsError()).toBe(true);
    expect(service.revisionCalls).toBe(2);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Topic practice analysis could not be loaded.',
    );
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Retry');

    fixture.detectChanges();
    fixture.detectChanges();
    expect(service.revisionCalls).toBe(2);

    service.revisionResult = of({
      completed_session_count: 0,
      activity: [],
      requested_session_limit: 30,
      sessions_used: 0,
      measured_learning_item_count: 0,
      weak_area_ready: false,
      minimum_attempts: 3,
      topic_attribution: 'CURRENT_LEARNING_ITEM_TOPICS',
      attribution_note: 'No completed sessions.',
      topic_practice: [],
    });
    component.loadInsights();
    fixture.detectChanges();

    expect(service.revisionCalls).toBe(3);
    expect(component.insightsLoading()).toBe(false);
    expect(component.insightsError()).toBe(false);
  });
});
