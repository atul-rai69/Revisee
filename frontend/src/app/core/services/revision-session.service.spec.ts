import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { RevisionSessionResponse, RevisionSessionResult } from '../models/revision.models';
import { RevisionSessionService } from './revision-session.service';

const sessionResponse: RevisionSessionResponse = {
  session_id: 7,
  requested_strategy: 'RANDOM',
  strategy_used: 'RANDOM',
  question_count: 1,
  questions_per_label: null,
  generated_question_count: 0,
  status: 'IN_PROGRESS',
  labels: null,
  questions: [{
    session_question_id: 31,
    position: 1,
    question: 'What is dependency injection?',
    options: [
      { label: 'A', text: 'A pattern' }, { label: 'B', text: 'A database' },
      { label: 'C', text: 'A browser' }, { label: 'D', text: 'A stylesheet' },
    ],
    difficulty: 2,
    expected_time_seconds: 30,
  }],
};

const resultResponse: RevisionSessionResult = {
  session_id: 7,
  status: 'COMPLETED',
  requested_strategy: 'RANDOM',
  strategy_used: 'RANDOM',
  started_at: null,
  completed_at: '2026-09-05T10:00:00Z',
  question_count: 1,
  correct_count: 1,
  incorrect_count: 0,
  score_percentage: 100,
  total_time_taken_seconds: 12,
  labels: null,
  questions: [],
};

describe('RevisionSessionService', () => {
  let service: RevisionSessionService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(RevisionSessionService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates RANDOM, LABEL, and SMART sessions with exact payloads', () => {
    const requests = [
      { quiz_type: 'RANDOM' as const, question_count: 10, allow_ai_generation: false as const },
      { quiz_type: 'LABEL' as const, label_ids: [2, 5], questions_per_label: 5, allow_ai_generation: false as const },
      { quiz_type: 'SMART' as const, question_count: 8, allow_ai_generation: false as const },
    ];

    requests.forEach((payload) => {
      service.createSession(payload).subscribe();
      const request = http.expectOne(`${environment.apiUrl}/revision-sessions`);
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual(payload);
      request.flush(sessionResponse);
    });
  });

  it('loads a persisted session', () => {
    service.getSession(7).subscribe((value) => expect(value).toEqual(sessionResponse));
    const request = http.expectOne(`${environment.apiUrl}/revision-sessions/7`);
    expect(request.request.method).toBe('GET');
    request.flush(sessionResponse);
  });

  it('submits the exact immutable session-question IDs', () => {
    const answers = [{ session_question_id: 31, selected_option: 'B' as const, time_taken_seconds: 12 }];
    service.submitSession(7, answers).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/revision-sessions/7/submit`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ answers });
    request.flush(resultResponse);
  });

  it('loads the canonical completed result', () => {
    service.getResult(7).subscribe((value) => expect(value).toEqual(resultResponse));
    const request = http.expectOne(`${environment.apiUrl}/revision-sessions/7/result`);
    expect(request.request.method).toBe('GET');
    request.flush(resultResponse);
  });
});
