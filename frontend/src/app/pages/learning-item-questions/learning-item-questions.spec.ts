import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Observable, of, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import { LearningItem, LearningItemResponse } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import { LearningItemQuestions } from './learning-item-questions';

const response: LearningItemResponse = {
  message: 'ok',
  data: {
    id: 5, title: 'Databases', description_text: 'Owned notes', labels: 'Backend',
    image_urls: null, pdf_urls: null, first_image_url: null, image_count: 0, pdf_count: 0,
    theory: null, key_points: [], created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z', hours_ago: 2,
    questions: [
      {
        number: 1, question: 'What is a primary key?', difficulty: 2,
        expected_time_seconds: 30, explanation: 'It uniquely identifies a row.',
        options: [
          { label: 'A', text: 'A row identifier', isCorrect: true },
          { label: 'B', text: 'A duplicate field', isCorrect: false },
          { label: 'C', text: 'A UI component', isCorrect: false },
          { label: 'D', text: 'A server', isCorrect: false },
        ],
      },
      {
        number: 2, question: 'What does a foreign key reference?', difficulty: 1,
        expected_time_seconds: 20, explanation: 'It references a key in another table.',
        options: [
          { label: 'A', text: 'A CSS class', isCorrect: false },
          { label: 'B', text: 'Another table key', isCorrect: true },
          { label: 'C', text: 'A browser route', isCorrect: false },
          { label: 'D', text: 'A password', isCorrect: false },
        ],
      },
    ],
  },
};

class FakeLearningItemService {
  getCalls = 0;
  detailResponse: Observable<LearningItemResponse> = of(response);
  readonly generation = new Subject<{ message: string }>();
  generateRevisionContent = vi.fn(() => this.generation.asObservable());
  getLearningItem() {
    this.getCalls += 1;
    return this.detailResponse;
  }
}

describe('LearningItemQuestions', () => {
  let fixture: ComponentFixture<LearningItemQuestions>;
  let component: LearningItemQuestions;
  let service: FakeLearningItemService;
  let routeId = '5';

  beforeEach(async () => {
    routeId = '5';
    await TestBed.configureTestingModule({
      imports: [LearningItemQuestions],
      providers: [
        ToasterService,
        { provide: LearningItem, useClass: FakeLearningItemService },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => routeId } } } },
      ],
    }).compileComponents();
    service = TestBed.inject(LearningItem) as unknown as FakeLearningItemService;
  });

  function createComponent(): void {
    fixture = TestBed.createComponent(LearningItemQuestions);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('shows every stored question but reveals correctness only on request', () => {
    createComponent();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('What is a primary key?');
    expect(element.textContent).toContain('What does a foreign key reference?');
    expect(element.querySelector('.option--correct')).toBeNull();
    const button = element.querySelector('.answer-toggle') as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
    expect(element.querySelector('.option--correct')?.textContent).toContain('A row identifier');
    expect(element.textContent).toContain('It uniquely identifies a row.');
  });

  it('prevents duplicate generation and refreshes the bank after success', () => {
    createComponent();
    component.generateMoreQuestions();
    component.generateMoreQuestions();
    expect(service.generateRevisionContent).toHaveBeenCalledTimes(1);
    expect(service.generateRevisionContent).toHaveBeenCalledWith(5, 'Databases', 'Owned notes');
    service.generation.next({ message: 'ok' });
    service.generation.complete();
    expect(service.getCalls).toBe(2);
  });

  it('shows safe local feedback and releases the busy state for a validation failure', () => {
    createComponent();
    const toaster = TestBed.inject(ToasterService);
    component.generateMoreQuestions();
    service.generation.error({ status: 422 });
    expect(component.generating()).toBe(false);
    expect(toaster.toasts()[0]?.title).toBe('Generation failed');
    expect(toaster.toasts()[0]?.message).not.toContain('422');
  });

  it('reactively ends loading when an asynchronous resume response arrives', async () => {
    const request = new Subject<LearningItemResponse>();
    service.detailResponse = request.asObservable();
    createComponent();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Loading all questions');

    request.next(response);
    request.complete();
    await fixture.whenStable();

    expect(component.loading()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('What is a primary key?');
  });

  it('ends loading and shows an error after a request failure', async () => {
    service.detailResponse = throwError(() => new HttpErrorResponse({ status: 404 }));
    createComponent();
    await fixture.whenStable();

    expect(component.loading()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('This learning item is unavailable');
  });

  it('renders an empty bank when the runtime questions collection is null', async () => {
    service.detailResponse = of({
      ...response,
      data: { ...response.data, questions: null },
    } as unknown as LearningItemResponse);
    createComponent();
    await fixture.whenStable();

    expect(component.loading()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No stored questions yet');
  });

  it('ends loading without a request for an invalid route ID', async () => {
    routeId = '0';
    createComponent();
    await fixture.whenStable();

    expect(service.getCalls).toBe(0);
    expect(component.loading()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('address is invalid');
  });
});
