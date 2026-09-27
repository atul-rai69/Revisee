import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { PdfQuestionOption } from '../../pages/pdf-question-import/pdf-question-parser';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export interface PdfSourcePageRequest {
  page_number: number;
  text: string;
}

export interface PdfQuestionDraftContract {
  question: string;
  options: Record<PdfQuestionOption, string>;
  correct_option: PdfQuestionOption | null;
  explanation: string | null;
  difficulty: number;
  expected_time_seconds: number;
  source_page: number;
  source_excerpt: string;
  confidence: number;
  validation_issues: string[];
}

export interface PdfDraftGenerationRequest {
  source_filename: string;
  mode: 'PARSE' | 'GENERATE';
  source_pages: PdfSourcePageRequest[];
  question_count: number;
  difficulty: number;
  focus_instructions: string | null;
  generation_source: 'REVISEE' | 'PERSONAL';
  credential_id: number | null;
}

export interface PdfDraftGenerationResponse {
  drafts: PdfQuestionDraftContract[];
  requested_count: number;
  returned_count: number;
  rejected_count: number;
  partial: boolean;
  coverage_page_numbers: number[];
}

export interface PdfQuestionImportResponse {
  inserted_count: number;
  duplicate_count: number;
  rejected_count: number;
  failed_count: number;
  inserted_question_ids: number[];
}

@Injectable({ providedIn: 'root' })
export class PdfQuestionImportService {
  private readonly apiUrl = environment.apiUrl;
  private readonly localContext = new HttpContext().set(SKIP_GLOBAL_LOADER, true);

  constructor(private readonly http: HttpClient) {}

  generateDrafts(
    itemId: number,
    request: PdfDraftGenerationRequest,
  ): Observable<PdfDraftGenerationResponse> {
    return this.http.post<PdfDraftGenerationResponse>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-question-drafts/generate`,
      request,
      { context: this.localContext },
    );
  }

  importQuestions(
    itemId: number,
    request: {
      source_filename: string;
      destination_learning_item_id: number;
      source_pages: PdfSourcePageRequest[];
      questions: PdfQuestionDraftContract[];
    },
  ): Observable<PdfQuestionImportResponse> {
    return this.http.post<PdfQuestionImportResponse>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-questions/import`,
      request,
      { context: this.localContext },
    );
  }
}
