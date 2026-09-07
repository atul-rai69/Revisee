import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Observable, of, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import { LearningItem, LearningItemResponse } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import { LearningItemView } from './learning-item-view';

const response: LearningItemResponse = {
  message: 'ok',
  data: {
    id: 12,
    title: 'Cell biology',
    description_text: '<p>Real saved notes</p>',
    labels: 'Biology, Science',
    image_urls: 'https://res.cloudinary.com/revisee/image/upload/cell.png',
    pdf_urls: 'https://res.cloudinary.com/revisee/raw/upload/notes.pdf, https://evil.example/notes.pdf, javascript:alert(1)',
    first_image_url: 'https://res.cloudinary.com/revisee/image/upload/cell.png',
    image_count: 1,
    pdf_count: 1,
    theory: 'Cell theory',
    key_points: ['Cells are structural units.'],
    questions: [{
      number: 1,
      question: 'What is a cell?',
      options: [
        { label: 'A', text: 'A unit of life', isCorrect: true },
        { label: 'B', text: 'A planet', isCorrect: false },
        { label: 'C', text: 'A language', isCorrect: false },
        { label: 'D', text: 'A metal', isCorrect: false },
      ],
      explanation: 'A cell is the basic structural unit of life.',
      difficulty: 1,
      expected_time_seconds: 20,
    }],
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-02T10:00:00Z',
    hours_ago: 24,
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

describe('LearningItemView', () => {
  let fixture: ComponentFixture<LearningItemView>;
  let component: LearningItemView;
  let service: FakeLearningItemService;
  let routeId = '12';

  beforeEach(async () => {
    routeId = '12';
    await TestBed.configureTestingModule({
      imports: [LearningItemView],
      providers: [
        ToasterService,
        { provide: LearningItem, useClass: FakeLearningItemService },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => routeId } } } },
      ],
    }).compileComponents();
    service = TestBed.inject(LearningItem) as unknown as FakeLearningItemService;
  });

  function createComponent(): void {
    fixture = TestBed.createComponent(LearningItemView);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  it('renders dynamic PDFs, counts, saved questions, and the all-questions route', () => {
    createComponent();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('notes.pdf');
    expect(element.textContent).toContain('1 PDF');
    expect(element.textContent).toContain('1 question');
    expect(element.textContent).toContain('What is a cell?');
    expect(element.querySelectorAll('iframe.pdf-preview')).toHaveLength(1);
    expect(element.querySelector('iframe.pdf-preview')?.hasAttribute('sandbox')).toBe(true);
    expect(element.querySelector('.answer-option.correct')).toBeNull();
    const viewAll = element.querySelector('a[href="/app/learning-items/12/questions"]');
    expect(viewAll).not.toBeNull();
    expect(component.pdfResources()).toHaveLength(1);
  });

  it('sends the real generation contract once and reloads after success', () => {
    createComponent();
    component.generateMoreQuestions();
    component.generateMoreQuestions();
    expect(service.generateRevisionContent).toHaveBeenCalledTimes(1);
    expect(service.generateRevisionContent).toHaveBeenCalledWith(12, 'Cell biology', '<p>Real saved notes</p>');
    service.generation.next({ message: 'ok' });
    service.generation.complete();
    fixture.detectChanges();
    expect(service.getCalls).toBe(2);
    expect(component.generating()).toBe(false);
  });

  it('reactively replaces the loader when an asynchronous response succeeds', async () => {
    const request = new Subject<LearningItemResponse>();
    service.detailResponse = request.asObservable();
    createComponent();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Loading your learning item');

    request.next(response);
    request.complete();
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(component.loading()).toBe(false);
    expect(element.textContent).toContain('Cell biology');
    expect(element.textContent).not.toContain('Loading your learning item');
  });

  it('normalizes nullable collections without preventing the item from rendering', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        labels: null,
        image_urls: null,
        pdf_urls: null,
        key_points: null,
        questions: null,
      },
    } as unknown as LearningItemResponse);
    createComponent();
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Cell biology');
    expect(element.textContent).toContain('No PDF has been attached');
    expect(element.textContent).toContain('No questions are stored yet');
    expect(component.loading()).toBe(false);
  });

  it('ends loading and shows a retryable error after an HTTP failure', async () => {
    service.detailResponse = throwError(() => new HttpErrorResponse({ status: 500 }));
    createComponent();
    await fixture.whenStable();

    let element = fixture.nativeElement as HTMLElement;
    expect(component.loading()).toBe(false);
    expect(element.textContent).toContain('The learning item could not be loaded');
    const retry = element.querySelector('button') as HTMLButtonElement;
    expect(retry.textContent).toContain('Try again');

    service.detailResponse = of(response);
    retry.click();
    await fixture.whenStable();
    element = fixture.nativeElement as HTMLElement;
    expect(service.getCalls).toBe(2);
    expect(element.textContent).toContain('Cell biology');
    expect(element.textContent).not.toContain('The learning item could not be loaded');
  });

  it('ends loading without requesting data for an invalid route ID', async () => {
    routeId = 'not-a-number';
    createComponent();
    await fixture.whenStable();

    expect(service.getCalls).toBe(0);
    expect(component.loading()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('address is invalid');
  });

  it('ignores unsafe PDF URLs without blocking the rest of the item', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        pdf_urls: 'not a URL,javascript:alert(1),https://example.com/file.pdf',
      },
    });
    createComponent();
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Cell biology');
    expect(element.querySelectorAll('iframe.pdf-preview')).toHaveLength(0);
    expect(element.textContent).toContain('No PDF has been attached');
  });
});
