import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export type MasteryEntityType = 'LABEL' | 'LEARNING_ITEM';
export type MasteryEvidenceStatus = 'NO_QUESTIONS' | 'NOT_ATTEMPTED' | 'INSUFFICIENT_EVIDENCE' | 'MEASURED';

export interface MasteryTrendPoint {
  session_id: number;
  recorded_at: string;
  score_before: number;
  score_after: number;
  total_attempts: number;
  correct_attempts: number;
}

export interface MasteryAnalyticsItem {
  entity_id: number;
  display_name: string;
  question_count: number;
  evidence_status: MasteryEvidenceStatus;
  mastery_score: number | null;
  total_attempts: number;
  correct_attempts: number;
  accuracy_percent: number | null;
  last_practised_at: string | null;
  next_review_at: string | null;
  trend: MasteryTrendPoint[];
}

export interface MasteryAnalyticsResponse {
  entity_type: MasteryEntityType;
  minimum_attempts: number;
  offset: number;
  limit: number;
  total: number;
  items: MasteryAnalyticsItem[];
}

export interface RevisionActivityPoint {
  date: string;
  completed_session_count: number;
  answered_count: number;
  correct_count: number;
  accuracy_percent: number | null;
}

export interface TopicPracticePoint {
  topic_id: number;
  topic_name: string;
  attempt_count: number;
  correct_count: number;
  accuracy_percent: number | null;
  session_count: number;
}

export interface RevisionAnalyticsResponse {
  completed_session_count: number;
  activity: RevisionActivityPoint[];
  requested_session_limit: 7 | 30 | 50;
  sessions_used: number;
  measured_learning_item_count: number;
  weak_area_ready: boolean;
  minimum_attempts: number;
  topic_attribution: 'CURRENT_LEARNING_ITEM_TOPICS';
  attribution_note: string;
  topic_practice: TopicPracticePoint[];
}

export interface WeakAreaItem {
  entity_id: number;
  display_name: string;
  mastery_score: number | null;
  total_attempts: number;
  correct_attempts: number;
  accuracy_percent: number | null;
  classification: 'DEMONSTRATED_WEAKNESS' | 'DUE_REVIEW' | 'INSUFFICIENT_EVIDENCE';
  reason: string;
}

export interface WeakAreasResponse {
  items: WeakAreaItem[];
  pagination: { offset: number; limit: number; total: number };
}

@Injectable({ providedIn: 'root' })
export class MasteryService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private readonly http: HttpClient) {}

  getAnalytics(entityType: MasteryEntityType, limit = 50, offset = 0): Observable<MasteryAnalyticsResponse> {
    return this.http.get<MasteryAnalyticsResponse>(`${this.apiUrl}/mastery/analytics`, {
      params: { entity_type: entityType, limit, offset },
      context: new HttpContext().set(SKIP_GLOBAL_LOADER, true),
    });
  }

  getRevisionAnalytics(sessionLimit: 7 | 30 | 50): Observable<RevisionAnalyticsResponse> {
    return this.http.get<RevisionAnalyticsResponse>(`${this.apiUrl}/analytics/revision-activity`, {
      params: { session_limit: sessionLimit },
      context: new HttpContext().set(SKIP_GLOBAL_LOADER, true),
    });
  }

  getWeakAreas(
    classification: 'DEMONSTRATED_WEAKNESS' | 'DUE_REVIEW',
    limit = 8,
  ): Observable<WeakAreasResponse> {
    return this.http.get<WeakAreasResponse>(`${this.apiUrl}/weak-areas`, {
      params: {
        entity_type: 'LEARNING_ITEM',
        classification,
        limit,
        offset: 0,
      },
      context: new HttpContext().set(SKIP_GLOBAL_LOADER, true),
    });
  }
}
