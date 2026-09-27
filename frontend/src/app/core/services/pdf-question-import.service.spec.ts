import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { PdfQuestionImportService } from './pdf-question-import.service';

describe('PdfQuestionImportService', () => {
  let service: PdfQuestionImportService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PdfQuestionImportService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('uses the item-bound local-PDF draft-generation contract', () => {
    const request = {
      source_filename: 'biology.pdf',
      mode: 'GENERATE' as const,
      source_pages: [{ page_number: 2, text: 'Grounded source text.' }],
      question_count: 3,
      difficulty: 2,
      focus_instructions: null,
      generation_source: 'REVISEE' as const,
      credential_id: null,
    };
    service.generateDrafts(12, request).subscribe();
    const call = http.expectOne(
      `${environment.apiUrl}/learning-items/12/pdf-question-drafts/generate`,
    );
    expect(call.request.method).toBe('POST');
    expect(call.request.body).toEqual(request);
    call.flush({ drafts: [], requested_count: 3, returned_count: 0, rejected_count: 0, partial: true, coverage_page_numbers: [2] });
  });

  it('uses a separate explicit import contract', () => {
    const request = {
      source_filename: 'biology.pdf',
      destination_learning_item_id: 14,
      source_pages: [{ page_number: 2, text: 'Grounded source text.' }],
      questions: [],
    };
    service.importQuestions(12, request).subscribe();
    const call = http.expectOne(
      `${environment.apiUrl}/learning-items/12/pdf-questions/import`,
    );
    expect(call.request.method).toBe('POST');
    expect(call.request.body).toEqual(request);
    call.flush({ inserted_count: 0, duplicate_count: 0, rejected_count: 0, failed_count: 0, inserted_question_ids: [] });
  });
});
