import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export type LearningItemOptionLabel = 'A' | 'B' | 'C' | 'D';

export interface LearningItemQuestionOption {
  label: LearningItemOptionLabel;
  text: string;
  isCorrect: boolean;
}

export interface LearningItemQuestion {
  number: number;
  question: string;
  options: LearningItemQuestionOption[];
  explanation: string | null;
  difficulty: number;
  expected_time_seconds: number;
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
  const question = value['question'];
  const difficulty = value['difficulty'];
  const expectedTime = value['expected_time_seconds'];
  if (
    typeof number !== 'number'
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
    number,
    question,
    options: options as LearningItemQuestionOption[],
    explanation: stringOrNull(value['explanation']),
    difficulty,
    expected_time_seconds: expectedTime,
  };
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
