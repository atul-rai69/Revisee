import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { DashboardService, DashboardSummary, LearningItemsSummaryResponse } from '../../core/services/dashboard-service';
import { LearningItemRecencyService } from '../../core/services/learning-item-recency.service';
import { MasteryService } from '../../core/services/mastery.service';
import { Dashboard, greetingForHour } from './dashboard';

const item = (id: number, title: string, labels = 'Biology'): LearningItemsSummaryResponse['data'][number] => ({
  id, title, description_text: '<p>Real notes preview</p>', labels,
  first_image_url: null, image_count: 2, pdf_count: 1, hours_ago: id,
});

class FakeDashboardService {
  summary: Observable<DashboardSummary> = of({ username: 'Atul', total_items: 5, total_labels: 2, login_streak: 4 });
  items: Observable<LearningItemsSummaryResponse> = of({ message: 'ok', data: [1, 2, 3, 4, 5].map((id) => item(id, `Item ${id}`)) });
  summaryCalls = 0;
  itemCalls = 0;
  getDashboardSummary(): Observable<DashboardSummary> { this.summaryCalls += 1; return this.summary; }
  getLearningItemSummary(): Observable<LearningItemsSummaryResponse> { this.itemCalls += 1; return this.items; }
}
class FakeMasteryService {
  getAnalytics(entityType: 'LABEL' | 'LEARNING_ITEM') {
    return of({ entity_type: entityType, minimum_attempts: 3, offset: 0, limit: 2, total: 1, items: [{
      entity_id: entityType === 'LABEL' ? 1 : 2, display_name: entityType === 'LABEL' ? 'Biology' : 'Item 2',
      question_count: 2, evidence_status: 'NOT_ATTEMPTED' as const, mastery_score: null,
      total_attempts: 0, correct_attempts: 0, accuracy_percent: null, last_practised_at: null,
      next_review_at: null, trend: [],
    }] });
  }
}
class FakeRecencyService {
  values = new Map<number, number>();
  exploredAt(id: number): number | null { return this.values.get(id) ?? null; }
}
class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('Dashboard', () => {
  let fixture: ComponentFixture<Dashboard>;
  let component: Dashboard;
  let dashboardService: FakeDashboardService;
  let recencyService: FakeRecencyService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        { provide: DashboardService, useClass: FakeDashboardService },
        { provide: MasteryService, useClass: FakeMasteryService },
        { provide: LearningItemRecencyService, useClass: FakeRecencyService },
        { provide: Router, useClass: FakeRouter },
      ],
    }).compileComponents();
    dashboardService = TestBed.inject(DashboardService) as unknown as FakeDashboardService;
    recencyService = TestBed.inject(LearningItemRecencyService) as unknown as FakeRecencyService;
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

  it('keeps the dashboard concise with four items and one analytics snapshot', () => {
    create();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Atul');
    expect(text).toContain('Recently added');
    expect(text).toContain('Mastery snapshot');
    expect(text).toContain('Item 1');
    expect(text).toContain('Item 4');
    expect(text).not.toContain('Item 5');
    expect(text).not.toContain('Revision activity and accuracy');
    expect(fixture.nativeElement.querySelectorAll('.learning-card')).toHaveLength(4);
  });

  it('prioritises items recently explored on this device', () => {
    recencyService.values.set(1, 1_000);
    recencyService.values.set(3, 3_000);
    create();
    expect(component.visibleItems().map((value) => value.id)).toEqual([3, 1]);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Recent activity on this device.');
  });

  it('routes dashboard actions to their dedicated destinations', () => {
    create();
    const router = TestBed.inject(Router) as unknown as FakeRouter;
    component.startRevision('RANDOM');
    component.startRevision('LABEL');
    component.viewLibrary();
    component.viewAnalytics();
    component.addMaterial();
    component.viewLearningItem(3);
    expect(router.navigate).toHaveBeenCalledWith(['/app/library']);
    expect(router.navigate).toHaveBeenCalledWith(['/app/analytics']);
    expect(router.navigate).toHaveBeenCalledWith(['/app/new-item']);
    expect(router.navigate).toHaveBeenCalledWith(['/app/learning-items', 3]);
  });

  it('shows honest empty and independent loading states', () => {
    dashboardService.summary = new Subject<DashboardSummary>();
    dashboardService.items = new Subject<LearningItemsSummaryResponse>();
    create();
    expect(fixture.nativeElement.querySelector('[aria-label="Loading your dashboard summary"]')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('[aria-label="Loading learning material"]')).toBeTruthy();
  });

  it('stops failed item loading and retries only when requested', () => {
    dashboardService.items = throwError(() => new Error('offline'));
    create();
    expect(component.itemsLoading()).toBe(false);
    expect(component.itemsError()).toBe(true);
    expect(dashboardService.itemCalls).toBe(1);
    fixture.detectChanges();
    expect(dashboardService.itemCalls).toBe(1);
    dashboardService.items = of({ message: 'ok', data: [] });
    component.loadItems();
    fixture.detectChanges();
    expect(dashboardService.itemCalls).toBe(2);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Add your first learning item');
  });
});
