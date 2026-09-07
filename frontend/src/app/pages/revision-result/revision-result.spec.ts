import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { RevisionSessionResult } from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { RevisionResult } from './revision-result';

const result: RevisionSessionResult = {
  session_id: 8, status: 'COMPLETED', requested_strategy: 'SMART', strategy_used: 'RANDOM',
  started_at: '2026-09-05T09:59:00Z', completed_at: '2026-09-05T10:00:00Z',
  question_count: 1, correct_count: 1, incorrect_count: 0, score_percentage: 100,
  total_time_taken_seconds: 12, labels: null,
  questions: [{
    session_question_id: 91, position: 1, learning_item_title: 'Angular basics', question: 'What is DI?',
    options: [{ label: 'A', text: 'A pattern' }, { label: 'B', text: 'A database' }, { label: 'C', text: 'A style' }, { label: 'D', text: 'A file' }],
    selected_option: 'A', correct_option: 'A', is_correct: true, explanation: 'Dependencies are supplied to consumers.',
    difficulty: 2, expected_time_seconds: 20, time_taken_seconds: 12, mastery_delta: 6.2,
  }],
};

class FakeResultService { getResult() { return of(result); } }
class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('RevisionResult', () => {
  let fixture: ComponentFixture<RevisionResult>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RevisionResult],
      providers: [
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => '8' } } } },
        { provide: Router, useClass: FakeRouter },
        { provide: RevisionSessionService, useClass: FakeResultService },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(RevisionResult);
    fixture.detectChanges();
  });

  it('renders canonical score, answers, explanation, mastery, and SMART fallback', () => {
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('100%');
    expect(text).toContain('A. A pattern');
    expect(text).toContain('Dependencies are supplied');
    expect(text).toContain('+6.2 mastery');
    expect(text).toContain('Smart revision used Quick revision');
  });
});
