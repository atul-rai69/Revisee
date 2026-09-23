import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';
import { GenerationChoice } from './ai-credentials.service';

export type LearningItemOptionLabel = 'A' | 'B' | 'C' | 'D';

export interface LearningItemQuestionOption {
  label: LearningItemOptionLabel;
  text: string;
  isCorrect: boolean;
}

export interface LearningItemQuestion {
  question_id: number;
  number: number;
  question: string;
  options: LearningItemQuestionOption[];
  explanation: string | null;
  difficulty: number;
  expected_time_seconds: number;
  total_attempts: number;
  correct_attempts: number;
  accuracy_percent: number | null;
}

export interface PdfResource {
  id: number;
  url: string;
  original_filename: string | null;
}

export interface PdfNote {
  id: number;
  learning_item_id: number;
  media_id: number;
  page_number: number;
  source_excerpt: string | null;
  note_text: string;
  created_at: string;
  updated_at: string;
}

export interface PdfNoteCreateRequest {
  media_id: number;
  page_number: number;
  source_excerpt: string | null;
  note_text: string;
}

export interface PdfNoteUpdateRequest {
  source_excerpt: string | null;
  note_text: string;
}

export interface ManualQuestionRequest {
  question: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  correct_option: LearningItemOptionLabel;
  explanation: string;
  difficulty: number;
  expected_time_seconds: number;
}

export interface ManualQuestionCreatedResponse {
  message: string;
  question_id: number;
}

export interface LearningItemDetail {
  id: number;
  title: string;
  description_text: string | null;
  created_at: string;
  updated_at: string;
  labels: string | null;
  image_urls: string | null;
  pdf_urls: string | null;
  pdf_resources?: PdfResource[];
  image_count: number;
  pdf_count: number;
  theory: string | null;
  key_points: string[];
  questions: LearningItemQuestion[];
  first_image_url: string | null;
  hours_ago: number;
}

export interface LearningItemResponse {
  message: string;
  data: LearningItemDetail;
}

export interface LearningItemMutationResponse {
  message: string;
}

export interface GenerateLearningItemRevisionRequest {
  learning_item_id: number;
  title: string;
  description: string;
}

export interface GenerateQuestionsRequest extends GenerationChoice {
  question_count: number;
}

export interface GeneratedQuestionsResponse {
  message: string;
  status: 'COMPLETED' | 'PARTIAL';
  requested_count: number;
  saved_count: number;
  duplicate_count: number;
}

type JsonObject = Record<string, unknown>;

const OPTION_LABELS: readonly LearningItemOptionLabel[] = ['A', 'B', 'C', 'D'];

function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function finiteNumberOr(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function normalizeQuestion(value: unknown): LearningItemQuestion | null {
  if (!isObject(value) || !Array.isArray(value['options'])) return null;

  const number = value['number'];
  const questionId = value['question_id'];
  const question = value['question'];
  const difficulty = value['difficulty'];
  const expectedTime = value['expected_time_seconds'];
  if (
    typeof questionId !== 'number'
    || !Number.isInteger(questionId)
    || questionId <= 0
    || typeof number !== 'number'
    || !Number.isInteger(number)
    || typeof question !== 'string'
    || typeof difficulty !== 'number'
    || !Number.isFinite(difficulty)
    || typeof expectedTime !== 'number'
    || !Number.isFinite(expectedTime)
  ) {
    return null;
  }

  const options = value['options'].map((option): LearningItemQuestionOption | null => {
    if (!isObject(option)) return null;
    const label = option['label'];
    const text = option['text'];
    if (
      typeof label !== 'string'
      || !OPTION_LABELS.includes(label as LearningItemOptionLabel)
      || typeof text !== 'string'
      || typeof option['isCorrect'] !== 'boolean'
    ) {
      return null;
    }
    return {
      label: label as LearningItemOptionLabel,
      text,
      isCorrect: option['isCorrect'],
    };
  });

  if (options.length !== 4 || options.some((option) => option === null)) return null;

  return {
    question_id: questionId,
    number,
    question,
    options: options as LearningItemQuestionOption[],
    explanation: stringOrNull(value['explanation']),
    difficulty,
    expected_time_seconds: expectedTime,
    total_attempts: finiteNumberOr(value['total_attempts'], 0),
    correct_attempts: finiteNumberOr(value['correct_attempts'], 0),
    accuracy_percent: typeof value['accuracy_percent'] === 'number'
      ? value['accuracy_percent']
      : null,
  };
}

function normalizePdfResource(value: unknown): PdfResource | null {
  if (!isObject(value)) return null;
  const id = value['id'];
  const url = value['url'];
  const originalFilename = value['original_filename'];
  return typeof id === 'number' && Number.isInteger(id) && id > 0 && typeof url === 'string'
    ? {
      id,
      url,
      original_filename: typeof originalFilename === 'string' && originalFilename.trim()
        ? originalFilename.trim()
        : null,
    }
    : null;
}

/** Normalize runtime data before templates iterate over response collections. */
export function normalizeLearningItemResponse(value: unknown): LearningItemResponse {
  if (!isObject(value) || !isObject(value['data'])) {
    throw new TypeError('Unexpected learning-item response.');
  }

  const data = value['data'];
  const id = data['id'];
  const title = data['title'];
  const createdAt = data['created_at'];
  const updatedAt = data['updated_at'];
  if (
    typeof id !== 'number'
    || !Number.isInteger(id)
    || id <= 0
    || typeof title !== 'string'
    || typeof createdAt !== 'string'
    || typeof updatedAt !== 'string'
  ) {
    throw new TypeError('Unexpected learning-item data.');
  }

  const rawQuestions = Array.isArray(data['questions']) ? data['questions'] : [];
  const questions = rawQuestions
    .map(normalizeQuestion)
    .filter((question): question is LearningItemQuestion => question !== null);

  return {
    message: typeof value['message'] === 'string' ? value['message'] : '',
    data: {
      id,
      title,
      description_text: stringOrNull(data['description_text']),
      created_at: createdAt,
      updated_at: updatedAt,
      labels: stringOrNull(data['labels']),
      image_urls: stringOrNull(data['image_urls']),
      pdf_urls: stringOrNull(data['pdf_urls']),
      pdf_resources: Array.isArray(data['pdf_resources'])
        ? data['pdf_resources']
          .map(normalizePdfResource)
          .filter((resource): resource is PdfResource => resource !== null)
        : [],
      image_count: finiteNumberOr(data['image_count'], 0),
      pdf_count: finiteNumberOr(data['pdf_count'], 0),
      theory: stringOrNull(data['theory']),
      key_points: Array.isArray(data['key_points'])
        ? data['key_points'].filter((entry): entry is string => typeof entry === 'string')
        : [],
      questions,
      first_image_url: stringOrNull(data['first_image_url']),
      hours_ago: finiteNumberOr(data['hours_ago'], 0),
    },
  };
}

@Injectable({ providedIn: 'root' })
export class LearningItem {
  private readonly apiUrl = environment.apiUrl;

  constructor(private readonly http: HttpClient) {}

  createLearningItem(formData: FormData): Observable<LearningItemMutationResponse> {
    return this.http.post<LearningItemMutationResponse>(
      `${this.apiUrl}/learning-items`,
      formData,
    );
  }

  getLearningItem(
    itemId: number,
    options: { localLoading?: boolean } = {},
  ): Observable<LearningItemResponse> {
    return this.http.get<unknown>(
      `${this.apiUrl}/learning-item/${itemId}`,
      { context: this.requestContext(options.localLoading) },
    ).pipe(map(normalizeLearningItemResponse));
  }

  generateRevisionContent(
    learningItemId: number,
    title: string,
    description: string,
  ): Observable<LearningItemMutationResponse> {
    const request: GenerateLearningItemRevisionRequest = {
      learning_item_id: learningItemId,
      title,
      description,
    };

    return this.http.post<LearningItemMutationResponse>(
      `${this.apiUrl}/generate`,
      request,
      { context: this.requestContext(true) },
    );
  }

  generateQuestions(
    learningItemId: number,
    request: GenerateQuestionsRequest,
  ): Observable<GeneratedQuestionsResponse> {
    return this.http.post<GeneratedQuestionsResponse>(
      `${this.apiUrl}/learning-items/${learningItemId}/generated-questions`,
      request,
      { context: this.requestContext(true) },
    );
  }

  createQuestion(itemId: number, request: ManualQuestionRequest): Observable<ManualQuestionCreatedResponse> {
    return this.http.post<ManualQuestionCreatedResponse>(
      `${this.apiUrl}/learning-items/${itemId}/questions`,
      request,
      { context: this.requestContext(true) },
    );
  }

  listPdfNotes(itemId: number): Observable<{ notes: PdfNote[] }> {
    return this.http.get<{ notes: PdfNote[] }>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-notes`,
      { context: this.requestContext(true) },
    );
  }

  createPdfNote(itemId: number, request: PdfNoteCreateRequest): Observable<PdfNote> {
    return this.http.post<PdfNote>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-notes`,
      request,
      { context: this.requestContext(true) },
    );
  }

  updatePdfNote(
    itemId: number,
    noteId: number,
    request: PdfNoteUpdateRequest,
  ): Observable<PdfNote> {
    return this.http.patch<PdfNote>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-notes/${noteId}`,
      request,
      { context: this.requestContext(true) },
    );
  }

  deletePdfNote(itemId: number, noteId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/learning-items/${itemId}/pdf-notes/${noteId}`,
      { context: this.requestContext(true) },
    );
  }

  deleteLearningItem(id: number): Observable<null> {
    return this.http.delete<null>(
      `${this.apiUrl}/learning-items`,
      { body: { id } },
    );
  }

  private requestContext(localLoading = false): HttpContext {
    return localLoading
      ? new HttpContext().set(SKIP_GLOBAL_LOADER, true)
      : new HttpContext();
  }
}
