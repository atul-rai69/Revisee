import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, of, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import { RevisionHistoryPage } from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { RevisionHistory } from './revision-history';

const page: RevisionHistoryPage = {
  offset: 0, limit: 10, total: 2,
  items: [
    { session_id: 2, status: 'IN_PROGRESS', requested_strategy: 'RANDOM', strategy_used: 'RANDOM', started_at: '2026-09-14T10:00:00Z', completed_at: null, question_count: 5, labels: null, correct_count: null, score_percentage: null, total_time_taken_seconds: null },
    { session_id: 1, status: 'COMPLETED', requested_strategy: 'LABEL', strategy_used: 'LABEL', started_at: '2026-09-13T10:00:00Z', completed_at: '2026-09-13T10:05:00Z', question_count: 4, labels: [{ label_id: 3, label_name: 'Angular', question_quota: 4 }], correct_count: 3, score_percentage: 75, total_time_taken_seconds: 90 },
  ],
};

class FakeService { response: Observable<RevisionHistoryPage> = of(page); getHistory = vi.fn(() => this.response); }
class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('RevisionHistory', () => {
  let fixture: ComponentFixture<RevisionHistory>;
  let service: FakeService;
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [RevisionHistory], providers: [{ provide: RevisionSessionService, useClass: FakeService }, { provide: Router, useClass: FakeRouter }] }).compileComponents();
    service = TestBed.inject(RevisionSessionService) as unknown as FakeService;
  });
  function create(): void { fixture = TestBed.createComponent(RevisionHistory); fixture.detectChanges(); }
  it('separates completed scores from active resume actions', () => {
    create(); const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('75%'); expect(text).toContain('View result'); expect(text).toContain('Resume revision');
  });
  it('terminates loading and exposes retry on errors', () => {
    service.response = throwError(() => new Error('offline')); create(); fixture.detectChanges();
    expect(fixture.componentInstance.loading()).toBe(false); expect((fixture.nativeElement as HTMLElement).textContent).toContain('Try again');
  });
  it('keeps loading visible until an asynchronous response arrives', () => {
    const pending = new Subject<RevisionHistoryPage>(); service.response = pending; create(); expect(fixture.componentInstance.loading()).toBe(true); pending.next(page); pending.complete(); expect(fixture.componentInstance.loading()).toBe(false);
  });
});
