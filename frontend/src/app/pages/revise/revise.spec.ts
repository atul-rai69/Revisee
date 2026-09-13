import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { RevisionSessionCreateRequest, RevisionSessionResponse } from '../../core/models/revision.models';
import { LabelService } from '../../core/services/label-service';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { ToasterService } from '../../core/services/toaster.service';
import { Revise } from './revise';
import { environment } from '../../../environments/environment';

const createdSession: RevisionSessionResponse = {
  session_id: 42,
  requested_strategy: 'RANDOM',
  strategy_used: 'RANDOM',
  question_count: 10,
  questions_per_label: null,
  generated_question_count: 0,
  status: 'IN_PROGRESS',
  labels: null,
  questions: [],
};

class FakeLabelService {
  getLabels(_options?: { localLoading?: boolean }) { return of([{ id: 2, user_id: 1, label_name: 'Angular' }, { id: 5, user_id: 1, label_name: 'Databases' }]); }
}

class FakeRevisionSessionService {
  lastRequest: RevisionSessionCreateRequest | null = null;
  calls = 0;
  result: Observable<RevisionSessionResponse> = of(createdSession);
  createSession(request: RevisionSessionCreateRequest): Observable<RevisionSessionResponse> {
    this.calls += 1;
    this.lastRequest = request;
    return this.result;
  }
}

class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('Revise setup', () => {
  let fixture: ComponentFixture<Revise>;
  let component: Revise;
  let service: FakeRevisionSessionService;

  beforeEach(async () => {
    environment.features.phase4SmartRevision = true;
    await TestBed.configureTestingModule({
      imports: [Revise],
      providers: [
        ToasterService,
        { provide: Router, useClass: FakeRouter },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } },
        },
        { provide: LabelService, useClass: FakeLabelService },
        { provide: RevisionSessionService, useClass: FakeRevisionSessionService },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Revise);
    component = fixture.componentInstance;
    service = TestBed.inject(RevisionSessionService) as unknown as FakeRevisionSessionService;
    fixture.detectChanges();
  });

  afterEach(() => {
    environment.features.phase4SmartRevision = false;
  });

  it('maps Quick revision to a RANDOM request', () => {
    component.form.controls.questionCount.setValue(12);
    component.startRevision();
    expect(service.lastRequest).toEqual({ quiz_type: 'RANDOM', question_count: 12, allow_ai_generation: false });
    expect((TestBed.inject(Router) as unknown as FakeRouter).navigate).toHaveBeenCalledWith(['/app/revision-sessions', 42]);
  });

  it('honors a supported dashboard strategy query parameter', async () => {
    TestBed.resetTestingModule();
    await TestBed.configureTestingModule({
      imports: [Revise],
      providers: [
        ToasterService,
        { provide: Router, useClass: FakeRouter },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({ strategy: 'LABEL' }) } },
        },
        { provide: LabelService, useClass: FakeLabelService },
        { provide: RevisionSessionService, useClass: FakeRevisionSessionService },
      ],
    }).compileComponents();
    const queryFixture = TestBed.createComponent(Revise);
    queryFixture.detectChanges();
    expect(queryFixture.componentInstance.strategy).toBe('LABEL');
  });

  it('prevents duplicate session creation while the first request is pending', () => {
    service.result = new Subject<RevisionSessionResponse>();
    component.startRevision();
    component.startRevision();
    expect(service.calls).toBe(1);
    expect(component.creating()).toBe(true);
  });

  it('maps selected Topics to LABEL IDs and questions-per-label', () => {
    component.selectStrategy('LABEL');
    component.toggleTopic(2);
    component.toggleTopic(5);
    component.form.controls.questionsPerLabel.setValue(4);
    component.startRevision();
    expect(service.lastRequest).toEqual({
      quiz_type: 'LABEL', label_ids: [2, 5], questions_per_label: 4, allow_ai_generation: false,
    });
  });

  it('maps Smart revision without promising AI generation', () => {
    component.selectStrategy('SMART');
    component.form.controls.questionCount.setValue(9);
    component.startRevision();
    expect(service.lastRequest).toEqual({ quiz_type: 'SMART', question_count: 9, allow_ai_generation: false });
  });

  it('rejects a Topic revision without a Topic selection', () => {
    component.selectStrategy('LABEL');
    component.startRevision();
    expect(service.lastRequest).toBeNull();
    expect(component.createError()?.kind).toBe('VALIDATION');
  });

  it('presents a structured insufficient-bank response as actionable setup guidance', () => {
    service.result = throwError(() => new HttpErrorResponse({
      status: 409,
      error: { detail: { code: 'INSUFFICIENT_QUESTION_BANK' } },
    }));
    component.startRevision();
    expect(component.createError()?.kind).toBe('INSUFFICIENT_QUESTIONS');
    expect(component.createError()?.message).toContain('fewer questions');
  });
});
