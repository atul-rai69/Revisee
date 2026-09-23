import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { DashboardService, DashboardSummary, LearningItemsSummaryResponse } from '../../core/services/dashboard-service';
import { Label, LabelService } from '../../core/services/label-service';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import {
  MasteryService,
  RevisionAnalyticsResponse,
} from '../../core/services/mastery.service';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { Dashboard, greetingForHour } from './dashboard';
import { AICredentialsService } from '../../core/services/ai-credentials.service';

class FakeDashboardService {
  summary: Observable<DashboardSummary> = of({ username: 'Atul', total_items: 1, total_labels: 2, login_streak: 4 });
  items: Observable<LearningItemsSummaryResponse> = of({
    message: 'ok',
    data: [{
      id: 8, title: 'Long-lived knowledge', description_text: '<p>Real notes preview</p>', labels: 'Biology, Writing',
      first_image_url: null, image_count: 2, pdf_count: 1, hours_ago: 25,
    }],
  });
  summaryCalls = 0;
  itemCalls = 0;
  getDashboardSummary(_options?: { localLoading?: boolean }): Observable<DashboardSummary> {
    this.summaryCalls += 1;
    return this.summary;
  }
  getLearningItemSummary(_options?: { localLoading?: boolean }): Observable<LearningItemsSummaryResponse> {
    this.itemCalls += 1;
    return this.items;
  }
}

class FakeLabelService {
  result: Observable<Label[]> = of([
    { id: 2, user_id: 1, label_name: 'Biology' },
    { id: 5, user_id: 1, label_name: 'Writing' },
  ]);
  calls = 0;
  getLabels(_options?: { localLoading?: boolean }): Observable<Label[]> {
    this.calls += 1;
    return this.result;
  }
}

class FakeLearningItemService { deleteLearningItem(_id: number) { return of(null); } }
class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }
class FakeRevisionSessionService {
  getHistory() {
    return of({ offset: 0, limit: 4, total: 0, items: [] });
  }
}
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
    attribution_note: 'Totals can overlap.',
    topic_practice: [],
  });
  getAnalytics(entityType: 'LABEL' | 'LEARNING_ITEM') { return of({ entity_type: entityType, minimum_attempts: 3, offset: 0, limit: 100, total: 0, items: [] }); }
  getRevisionAnalytics(_sessionLimit: 7 | 30 | 50) {
    this.revisionCalls += 1;
    return this.revisionResult;
  }
}
class FakeAICredentialsService {
  list() { return of({ credentials: [], provider_console_url: 'https://aistudio.google.com/usage', quota_remaining_available: false as const }); }
}

describe('Dashboard', () => {
  let fixture: ComponentFixture<Dashboard>;
  let component: Dashboard;
  let dashboardService: FakeDashboardService;
  let labelService: FakeLabelService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        ToasterService,
        { provide: DashboardService, useClass: FakeDashboardService },
        { provide: LabelService, useClass: FakeLabelService },
        { provide: LearningItem, useClass: FakeLearningItemService },
        { provide: RevisionSessionService, useClass: FakeRevisionSessionService },
        { provide: MasteryService, useClass: FakeMasteryService },
        { provide: AICredentialsService, useClass: FakeAICredentialsService },
        { provide: Router, useClass: FakeRouter },
      ],
    }).compileComponents();
    dashboardService = TestBed.inject(DashboardService) as unknown as FakeDashboardService;
    labelService = TestBed.inject(LabelService) as unknown as FakeLabelService;
  });

  function create(): void {
    fixture = TestBed.createComponent(Dashboard);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('uses deterministic time-aware greeting boundaries', () => {
    expect(greetingForHour(6)).toBe('Good morning');
    expect(greetingForHour(12)).toBe('Good afternoon');
    expect(greetingForHour(18)).toBe('Good evening');
  });

  it('renders real summary, Topic, and learning-item responses', () => {
    create();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Atul');
    expect(text).toContain('Biology');
    expect(text).toContain('Long-lived knowledge');
    expect(text).toContain('Real notes preview');
    expect(text).toContain('2 images');
    expect(text).toContain('1 PDF');
    expect(text).not.toContain('Recently Viewed');
    expect(text).not.toContain('Items Reviewed');
    expect(text).not.toContain('Topic Overview');
    expect(text).not.toContain('Continue revision');
  });

  it('searches the currently loaded items and Topics', () => {
    create();
    const input = fixture.nativeElement.querySelector('#library-search') as HTMLInputElement;
    input.value = 'writing';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Long-lived knowledge');
    input.value = 'missing';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No matching material');
  });

  it('routes revision strategies and contextual actions without duplicating setup', () => {
    create();
    const router = TestBed.inject(Router) as unknown as FakeRouter;
    component.startRevision('RANDOM');
    component.startRevision('LABEL');
    component.viewTopics();
    component.addMaterial();
    component.viewLearningItem(8);
    expect(router.navigate).toHaveBeenNthCalledWith(1, ['/app/revise'], { queryParams: { strategy: 'RANDOM' } });
    expect(router.navigate).toHaveBeenNthCalledWith(2, ['/app/revise'], { queryParams: { strategy: 'LABEL' } });
    expect(router.navigate).toHaveBeenCalledWith(['/app/labels']);
    expect(router.navigate).toHaveBeenCalledWith(['/app/new-item']);
    expect(router.navigate).toHaveBeenCalledWith(['/app/learning-items', 8]);
  });

  it('renders honest empty states', () => {
    dashboardService.items = of({ message: 'ok', data: [] });
    labelService.result = of([]);
    create();
    expect(fixture.nativeElement.textContent).toContain('No Topics yet');
    expect(fixture.nativeElement.textContent).toContain('Add your first learning item');
    expect(fixture.nativeElement.textContent).toContain('No completed revisions yet');
  });

  it('keeps independent section dimensions while requests are pending', () => {
    dashboardService.summary = new Subject<DashboardSummary>();
    dashboardService.items = new Subject<LearningItemsSummaryResponse>();
    labelService.result = new Subject<Label[]>();
    create();
    expect(fixture.nativeElement.querySelector('[aria-label="Loading your dashboard summary"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[aria-label="Loading Topics"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[aria-label="Loading learning material"]')).toBeTruthy();
  });

  it('shows section-level errors and retries independently', () => {
    dashboardService.summary = throwError(() => new Error('offline'));
    dashboardService.items = throwError(() => new Error('offline'));
    labelService.result = throwError(() => new Error('offline'));
    create();
    expect(fixture.nativeElement.textContent).toContain('Dashboard totals could not be loaded.');
    expect(fixture.nativeElement.textContent).toContain('Topics could not be loaded.');
    expect(fixture.nativeElement.textContent).toContain('learning material could not be loaded.');
    dashboardService.summary = of({ username: 'Recovered', total_items: 0, total_labels: 0, login_streak: 1 });
    component.loadSummary();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Recovered');
    expect(dashboardService.summaryCalls).toBe(2);
  });

  it('stops the analytics loader after an error and retries only on request', () => {
    const masteryService = TestBed.inject(MasteryService) as unknown as FakeMasteryService;
    masteryService.revisionResult = throwError(() => new Error('contract failure'));
    create();

    expect(component.analysisLoading()).toBe(false);
    expect(component.analysisError()).toBe(true);
    expect(masteryService.revisionCalls).toBe(1);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Revision analysis could not be loaded.',
    );
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Retry');

    fixture.detectChanges();
    fixture.detectChanges();
    expect(masteryService.revisionCalls).toBe(1);

    masteryService.revisionResult = of({
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
    component.loadAnalysis();
    fixture.detectChanges();

    expect(masteryService.revisionCalls).toBe(2);
    expect(component.analysisLoading()).toBe(false);
    expect(component.analysisError()).toBe(false);
  });
});
