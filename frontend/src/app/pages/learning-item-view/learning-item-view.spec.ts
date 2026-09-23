import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap, ParamMap, provideRouter, Router } from '@angular/router';
import { BehaviorSubject, Observable, of, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import { LearningItem, LearningItemResponse, PdfNote } from '../../core/services/learning-item';
import { DictionaryService } from '../../core/services/dictionary.service';
import { ToasterService } from '../../core/services/toaster.service';
import { PdfJsLoaderService } from '../../shared/components/pdf-viewer/pdfjs-loader.service';
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
      question_id: 21,
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
      total_attempts: 0,
      correct_attempts: 0,
      accuracy_percent: null,
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
  notes: PdfNote[] = [];
  readonly noteSave = new Subject<PdfNote>();
  listPdfNotes = vi.fn(() => of({ notes: this.notes }));
  createPdfNote = vi.fn(() => this.noteSave.asObservable());
  updatePdfNote = vi.fn(() => this.noteSave.asObservable());
  deletePdfNote = vi.fn(() => of(undefined));
}

describe('LearningItemView', () => {
  let fixture: ComponentFixture<LearningItemView>;
  let component: LearningItemView;
  let service: FakeLearningItemService;
  let routeId = '12';
  let routeParams: BehaviorSubject<ParamMap>;

  beforeEach(async () => {
    routeId = '12';
    routeParams = new BehaviorSubject(convertToParamMap({ id: routeId }));
    await TestBed.configureTestingModule({
      imports: [LearningItemView],
      providers: [
        provideRouter([]),
        ToasterService,
        { provide: LearningItem, useClass: FakeLearningItemService },
        { provide: DictionaryService, useValue: { lookup: vi.fn() } },
        { provide: ActivatedRoute, useValue: { paramMap: routeParams.asObservable() } },
        {
          provide: PdfJsLoaderService,
          useValue: {
            load: () => Promise.reject(new Error('PDF rendering is isolated here.')),
            assetUrl: (path: string) => `/assets/pdfjs/${path}`,
          },
        },
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
    expect(element.querySelectorAll('app-pdf-viewer')).toHaveLength(1);
    const openPdf = element.querySelector<HTMLAnchorElement>('.resource-download-btn');
    expect(openPdf?.href).toBe('https://res.cloudinary.com/revisee/raw/upload/notes.pdf');
    expect(element.querySelector('.answer-option.correct')).toBeNull();
    const viewAll = element.querySelector('a[href="/app/learning-items/12/questions"]');
    expect(viewAll).not.toBeNull();
    expect(component.pdfResources()).toHaveLength(1);
  });

  it('routes question generation through the append-only question bank flow', () => {
    createComponent();
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    component.generateMoreQuestions();
    expect(navigate).toHaveBeenCalledWith(['/app/learning-items', 12, 'questions']);
    expect(service.generateRevisionContent).not.toHaveBeenCalled();
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
    routeParams.next(convertToParamMap({ id: routeId }));
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
    expect(element.querySelectorAll('app-pdf-viewer')).toHaveLength(0);
    expect(element.textContent).toContain('not from approved Revisee storage');
  });

  it('supports multiple PDFs with an accessible selected attachment', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        pdf_urls: [
          'https://res.cloudinary.com/revisee/raw/upload/first.pdf',
          'https://res.cloudinary.com/revisee/raw/upload/second.pdf',
        ].join(','),
        pdf_count: 2,
      },
    });
    createComponent();
    await fixture.whenStable();

    const element = fixture.nativeElement as HTMLElement;
    const selectors = element.querySelectorAll<HTMLButtonElement>('.pdf-selector button');
    expect(selectors).toHaveLength(2);
    expect(component.selectedPdf()?.name).toBe('first.pdf');
    selectors[1].click();
    fixture.detectChanges();

    expect(component.selectedPdf()?.name).toBe('second.pdf');
    expect(selectors[1].getAttribute('aria-pressed')).toBe('true');
    expect(element.querySelectorAll('app-pdf-viewer')).toHaveLength(1);
  });

  it('clears the selected PDF when Angular reuses the page for another item', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        pdf_urls: [
          'https://res.cloudinary.com/revisee/raw/upload/first.pdf',
          'https://res.cloudinary.com/revisee/raw/upload/second.pdf',
        ].join(','),
        pdf_count: 2,
      },
    });
    createComponent();
    component.selectPdf(1);
    expect(component.selectedPdf()?.name).toBe('second.pdf');

    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        id: 13,
        title: 'A different item',
        pdf_urls: 'https://res.cloudinary.com/revisee/raw/upload/different.pdf',
        pdf_count: 1,
      },
    });
    routeParams.next(convertToParamMap({ id: '13' }));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.item()?.id).toBe(13);
    expect(component.selectedPdfIndex()).toBe(0);
    expect(component.selectedPdf()?.name).toBe('different.pdf');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('second.pdf');
  });

  it('ignores a stale detail response after switching items', async () => {
    const firstRequest = new Subject<LearningItemResponse>();
    const secondRequest = new Subject<LearningItemResponse>();
    service.detailResponse = firstRequest;
    createComponent();

    service.detailResponse = secondRequest;
    routeParams.next(convertToParamMap({ id: '13' }));
    secondRequest.next({
      ...response,
      data: {
        ...response.data,
        id: 13,
        title: 'Current item',
        pdf_urls: 'https://res.cloudinary.com/revisee/raw/upload/current.pdf',
      },
    });
    secondRequest.complete();
    firstRequest.next(response);
    firstRequest.complete();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.item()?.id).toBe(13);
    expect(component.selectedPdf()?.name).toBe('current.pdf');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('notes.pdf');
  });

  it('creates an explicitly reviewed PDF note and prevents duplicate saves', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        pdf_resources: [{
          id: 31,
          url: 'https://res.cloudinary.com/revisee/raw/upload/cloudinary-id.pdf',
          original_filename: 'Biology Revision Notes.pdf',
        }],
      },
    });
    createComponent();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Biology Revision Notes.pdf');
    component.openNoteEditor({ attachmentId: 31, pageNumber: 2, text: 'Selected passage' });
    fixture.detectChanges();
    const viewer = (fixture.nativeElement as HTMLElement).querySelector('app-pdf-viewer');
    const readingNoteEditor = viewer?.querySelector('.pdf-note-editor');
    expect(readingNoteEditor).not.toBeNull();
    expect((fixture.nativeElement as HTMLElement).querySelector('.pdf-note-editor-backdrop')).toBeNull();
    component.noteForm.controls.noteText.setValue('My own explanation');
    component.savePdfNote();
    component.savePdfNote();

    expect(service.createPdfNote).toHaveBeenCalledTimes(1);
    expect(service.createPdfNote).toHaveBeenCalledWith(12, {
      media_id: 31,
      page_number: 2,
      source_excerpt: 'Selected passage',
      note_text: 'My own explanation',
    });
    service.noteSave.next({
      id: 7,
      learning_item_id: 12,
      media_id: 31,
      page_number: 2,
      source_excerpt: 'Selected passage',
      note_text: 'My own explanation',
      created_at: '2026-09-20T10:00:00Z',
      updated_at: '2026-09-20T10:00:00Z',
    });
    service.noteSave.complete();
    fixture.detectChanges();
    expect(component.noteEditorOpen()).toBe(false);
  });

  it('clears an unsaved note and page request when switching PDFs or items', async () => {
    service.detailResponse = of({
      ...response,
      data: {
        ...response.data,
        pdf_resources: [
          { id: 31, url: 'https://res.cloudinary.com/revisee/raw/upload/first.pdf', original_filename: 'First notes.pdf' },
          { id: 32, url: 'https://res.cloudinary.com/revisee/raw/upload/second.pdf', original_filename: 'Second notes.pdf' },
        ],
      },
    });
    createComponent();
    component.openNoteEditor({ attachmentId: 31, pageNumber: 4, text: 'First PDF text' });
    component.selectPdf(1);
    expect(component.noteEditorOpen()).toBe(false);
    expect(component.noteAttachmentId()).toBe(0);

    service.detailResponse = of({
      ...response,
      data: { ...response.data, id: 13, title: 'Other item', pdf_resources: [] },
    });
    routeParams.next(convertToParamMap({ id: '13' }));
    await fixture.whenStable();
    expect(component.pdfNotes()).toEqual([]);
    expect(component.pageRequest()).toBeNull();
  });
});
