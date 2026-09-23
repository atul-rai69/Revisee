import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subject, of } from 'rxjs';
import { vi } from 'vitest';
import { RevisionSessionResponse, RevisionSessionResult, RevisionSubmissionAnswer } from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { ToasterService } from '../../core/services/toaster.service';
import { RevisionSession } from './revision-session';
import { environment } from '../../../environments/environment';

const activeSession: RevisionSessionResponse = {
  session_id: 8,
  requested_strategy: 'LABEL',
  strategy_used: 'LABEL',
  question_count: 2,
  questions_per_label: 2,
  generated_question_count: 0,
  status: 'IN_PROGRESS',
  labels: [{ label_id: 3, label_name: 'Angular', question_quota: 2 }],
  questions: [
    { session_question_id: 91, position: 1, question: 'First?', options: [{ label: 'A', text: 'One' }, { label: 'B', text: 'Two' }, { label: 'C', text: 'Three' }, { label: 'D', text: 'Four' }], difficulty: 1, expected_time_seconds: 20 },
    { session_question_id: 92, position: 2, question: 'Second?', options: [{ label: 'A', text: 'Alpha' }, { label: 'B', text: 'Beta' }, { label: 'C', text: 'Gamma' }, { label: 'D', text: 'Delta' }], difficulty: 2, expected_time_seconds: 30 },
  ],
};

const completedResult: RevisionSessionResult = {
  session_id: 8, status: 'COMPLETED', requested_strategy: 'LABEL', strategy_used: 'LABEL',
  started_at: null, completed_at: '2026-09-05T10:00:00Z', question_count: 2,
  correct_count: 1, incorrect_count: 1, score_percentage: 50, total_time_taken_seconds: 3,
  labels: [{ label_id: 3, label_name: 'Angular', question_quota: 2 }], questions: [],
};

class FakeRevisionSessionService {
  session = activeSession;
  submitResult: Observable<RevisionSessionResult> = of(completedResult);
  submitted: RevisionSubmissionAnswer[] | null = null;
  calls = 0;
  getSession() { return of(this.session); }
  submitSession(_sessionId: number, answers: RevisionSubmissionAnswer[]) {
    this.calls += 1;
    this.submitted = answers;
    return this.submitResult;
  }
}

class FakeRouter {
  navigate = vi.fn().mockResolvedValue(true);
}

describe('RevisionSession runner', () => {
  let fixture: ComponentFixture<RevisionSession>;
  let component: RevisionSession;
  let service: FakeRevisionSessionService;
  let router: FakeRouter;

  beforeEach(async () => {
    environment.features.phase3Results = true;
    vi.useFakeTimers();
    await TestBed.configureTestingModule({
      imports: [RevisionSession],
      providers: [
        ToasterService,
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => '8' } } } },
        { provide: Router, useClass: FakeRouter },
        { provide: RevisionSessionService, useClass: FakeRevisionSessionService },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(RevisionSession);
    component = fixture.componentInstance;
    service = TestBed.inject(RevisionSessionService) as unknown as FakeRevisionSessionService;
    router = TestBed.inject(Router) as unknown as FakeRouter;
    fixture.detectChanges();
  });

  afterEach(() => {
    environment.features.phase3Results = true;
    fixture.destroy();
    vi.useRealTimers();
  });

  it('renders answer-safe questions in backend order and supports previous/next navigation', () => {
    expect(component.currentQuestion?.session_question_id).toBe(91);
    component.next();
    expect(component.currentQuestion?.session_question_id).toBe(92);
    component.previous();
    expect(component.currentQuestion?.session_question_id).toBe(91);
    const text = fixture.nativeElement.textContent as string;
    expect(text).not.toContain('Correct answer');
    expect(text).not.toContain('Explanation');
  });

  it('shows the submit action on the final question', () => {
    component.next();
    fixture.detectChanges();

    const buttons = Array.from(fixture.nativeElement.querySelectorAll('button')) as HTMLButtonElement[];
    expect(buttons.some((button) => button.textContent?.trim() === 'Submit revision')).toBe(true);
  });

  it('keys answers by session_question_id and includes measured time', () => {
    component.selectOption('B');
    vi.advanceTimersByTime(2000);
    component.next();
    component.selectOption('D');
    vi.advanceTimersByTime(1000);
    component.requestSubmission();
    component.confirmSubmission();
    expect(service.submitted).toEqual([
      { session_question_id: 91, selected_option: 'B', time_taken_seconds: 2 },
      { session_question_id: 92, selected_option: 'D', time_taken_seconds: 1 },
    ]);
  });

  it('does not submit until every question is answered', () => {
    component.selectOption('A');
    component.requestSubmission();
    component.confirmSubmission();
    expect(service.calls).toBe(0);
  });

  it('prevents duplicate submission while a request is pending', () => {
    const pending = new Subject<RevisionSessionResult>();
    service.submitResult = pending;
    component.selectOption('A');
    component.next();
    component.selectOption('B');
    component.confirmSubmission();
    component.confirmSubmission();
    expect(service.calls).toBe(1);
    pending.next(completedResult);
    pending.complete();
  });

  it('redirects completed sessions to their canonical result', () => {
    service.session = { ...activeSession, status: 'COMPLETED' };
    component.loadSession();
    expect(router.navigate).toHaveBeenCalledWith(['/app/revision-sessions', 8, 'result'], { replaceUrl: true });
  });

  it('warns before exiting when answers have not been submitted', () => {
    component.selectOption('A');
    component.requestExit();
    expect(component.showExitDialog()).toBe(true);
    component.showExitDialog.set(false);
    expect(router.navigate).not.toHaveBeenCalledWith(['/app/revise']);
  });
});
