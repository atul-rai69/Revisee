import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject } from 'rxjs';
import { ActivatedRoute } from '@angular/router';
import { AICredentialsService } from '../../core/services/ai-credentials.service';
import { DashboardService } from '../../core/services/dashboard-service';
import { LearningItem, LearningItemResponse } from '../../core/services/learning-item';
import { PdfQuestionImportService } from '../../core/services/pdf-question-import.service';
import { PdfTextExtractorService } from '../../shared/components/pdf-viewer/pdf-text-extractor.service';
import { PdfQuestionImport } from './pdf-question-import';

const detail: LearningItemResponse = {
  message: 'ok',
  data: {
    id: 12,
    title: 'Biology',
    description_text: null,
    labels: null,
    image_urls: null,
    pdf_urls: null,
    pdf_resources: [{ id: 31, url: 'https://res.cloudinary.com/revisee/raw/upload/questions.pdf', original_filename: 'Questions.pdf' }],
    first_image_url: null,
    image_count: 0,
    pdf_count: 1,
    theory: null,
    key_points: [],
    questions: [],
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    hours_ago: 1,
  },
};

class LearningItemsStub {
  getLearningItem = vi.fn(() => of(detail));
}

class DashboardStub {
  getLearningItemSummary = vi.fn(() => of({ message: 'ok', data: [{
    id: 12, title: 'Biology', description_text: null, labels: null,
    first_image_url: null, image_count: 0, pdf_count: 1, hours_ago: 1,
  }] }));
}

class CredentialsStub {
  list = vi.fn(() => of({ credentials: [], provider_console_url: '', quota_remaining_available: false as const }));
}

class ExtractorStub {
  inspect = vi.fn(() => Promise.resolve(1));
  extract = vi.fn(() => Promise.resolve({
    pageCount: 1,
    pages: [{
      page_number: 1,
      text: '1. Pick one?\nA. One\nB. Two\nC. Three\nD. Four\nAnswer: A\nExplanation: One is stated.',
      has_usable_text: true,
    }],
    scannedPageNumbers: [],
    totalCharacters: 90,
  }));
}

class PdfQuestionsStub {
  readonly importResponse = new Subject<{
    inserted_count: number; duplicate_count: number; rejected_count: number;
    failed_count: number; inserted_question_ids: number[];
  }>();
  generateDrafts = vi.fn(() => of({
    drafts: [], requested_count: 5, returned_count: 0, rejected_count: 0,
    partial: true, coverage_page_numbers: [1],
  }));
  importQuestions = vi.fn(() => this.importResponse.asObservable());
}

describe('PdfQuestionImport', () => {
  let fixture: ComponentFixture<PdfQuestionImport>;
  let component: PdfQuestionImport;
  let extractor: ExtractorStub;
  let pdfQuestions: PdfQuestionsStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PdfQuestionImport],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: {
          paramMap: { get: (key: string) => key === 'learningItemId' ? '12' : null },
          queryParamMap: { get: () => null },
        } } },
        { provide: LearningItem, useClass: LearningItemsStub },
        { provide: DashboardService, useClass: DashboardStub },
        { provide: AICredentialsService, useClass: CredentialsStub },
        { provide: PdfTextExtractorService, useClass: ExtractorStub },
        { provide: PdfQuestionImportService, useClass: PdfQuestionsStub },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(PdfQuestionImport);
    component = fixture.componentInstance;
    extractor = TestBed.inject(PdfTextExtractorService) as unknown as ExtractorStub;
    pdfQuestions = TestBed.inject(PdfQuestionImportService) as unknown as PdfQuestionsStub;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  async function selectValidPdf(): Promise<void> {
    await component.selectPdfFile(new File(
      [new Uint8Array(100)],
      'Questions.pdf',
      { type: 'application/pdf' },
    ));
    fixture.detectChanges();
  }

  it('extracts editable drafts and exposes accessible workflow labels', async () => {
    await selectValidPdf();
    await component.startWorkflow();
    fixture.detectChanges();

    expect(component.workflowState()).toBe('REVIEW');
    expect(component.drafts()).toHaveLength(1);
    expect(component.drafts()[0].question).toBe('Pick one?');
    component.updateOption(
      component.drafts()[0].clientId,
      'D',
      { target: { value: 'Edited fourth option' } } as unknown as Event,
    );
    component.toggleDraft(component.drafts()[0].clientId, false);
    expect(component.drafts()[0].options.D).toBe('Edited fourth option');
    expect(component.drafts()[0].selected).toBe(false);
    component.toggleDraft(component.drafts()[0].clientId, true);
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[aria-labelledby="review-heading"]')).not.toBeNull();
    expect(element.textContent).toContain('Extract existing questions');
    expect(element.textContent).toContain('Generate from PDF only');
    expect(pdfQuestions.importQuestions).not.toHaveBeenCalled();
  });

  it('shows mode-specific guidance for preparing a compatible PDF', async () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[aria-labelledby="best-results-heading"]')).not.toBeNull();
    expect(element.textContent).toContain('Use a text-based PDF');
    expect(element.textContent).toContain('answer key on a later page');
    expect(element.textContent).toContain('Answer: B');

    (element.querySelector('input[value="GENERATE"]') as HTMLInputElement).click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(element.textContent).toContain('Best PDF content for grounded generation');
    expect(element.textContent).toContain('returns fewer drafts');
  });

  it('validates a local PDF and defaults the destination to the current item', async () => {
    await selectValidPdf();

    expect(extractor.inspect).toHaveBeenCalledOnce();
    expect(component.selectedFile()?.name).toBe('Questions.pdf');
    expect(component.filePageCount()).toBe(1);
    expect(component.importForm.controls.destinationId.value).toBe(12);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('not uploaded to Cloudinary');
  });

  it('rejects an invalid local file before PDF.js inspection', async () => {
    await component.selectPdfFile(new File(['plain'], 'questions.txt', { type: 'text/plain' }));
    fixture.detectChanges();

    expect(component.selectedFile()).toBeNull();
    expect(extractor.inspect).not.toHaveBeenCalled();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('Choose a PDF file');
  });

  it('sends the local filename and page-aware text for grounded generation', async () => {
    await selectValidPdf();
    component.setupForm.controls.mode.setValue('GENERATE');
    await component.startWorkflow();

    expect(pdfQuestions.generateDrafts).toHaveBeenCalledWith(12, expect.objectContaining({
      source_filename: 'Questions.pdf',
      mode: 'GENERATE',
      source_pages: [expect.objectContaining({ page_number: 1 })],
    }));
  });

  it('cancels stale inspection when the user chooses another PDF', async () => {
    let finishFirst: ((value: number) => void) | undefined;
    extractor.inspect
      .mockImplementationOnce(() => new Promise<number>((resolve) => { finishFirst = resolve; }))
      .mockResolvedValueOnce(3);
    const first = component.selectPdfFile(new File(
      [new Uint8Array(50)], 'First.pdf', { type: 'application/pdf' },
    ));
    await Promise.resolve();
    await component.selectPdfFile(new File(
      [new Uint8Array(50)], 'Second.pdf', { type: 'application/pdf' },
    ));
    finishFirst?.(2);
    await first;

    expect(component.selectedFile()?.name).toBe('Second.pdf');
    expect(component.filePageCount()).toBe(3);
  });

  it('prevents duplicate imports and finalizes after success', async () => {
    await selectValidPdf();
    await component.startWorkflow();
    component.importSelected();
    component.importSelected();
    expect(pdfQuestions.importQuestions).toHaveBeenCalledTimes(1);
    expect(component.importing()).toBe(true);

    pdfQuestions.importResponse.next({
      inserted_count: 1,
      duplicate_count: 0,
      rejected_count: 0,
      failed_count: 0,
      inserted_question_ids: [91],
    });
    pdfQuestions.importResponse.complete();
    await fixture.whenStable();

    expect(component.importing()).toBe(false);
    expect(component.importResult()?.inserted_count).toBe(1);
  });

  it('returns to setup with a visible error when extraction fails', async () => {
    await selectValidPdf();
    extractor.extract.mockRejectedValueOnce(new Error('offline'));
    await component.startWorkflow();
    fixture.detectChanges();

    expect(component.workflowState()).toBe('SETUP');
    expect(component.isBusy()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('could not be read');
  });
});
