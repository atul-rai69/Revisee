import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  RevisionSessionCreateRequest,
  RevisionHistoryPage,
  RevisionStatus,
  SmartReadiness,
  RevisionSessionResponse,
  RevisionSessionResult,
  RevisionSubmissionAnswer,
  RevisionSubmissionRequest,
} from '../models/revision.models';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

@Injectable({ providedIn: 'root' })
export class RevisionSessionService {
  private readonly apiUrl = environment.apiUrl;

  constructor(private readonly http: HttpClient) {}

  createSession(request: RevisionSessionCreateRequest): Observable<RevisionSessionResponse> {
    return this.http.post<RevisionSessionResponse>(`${this.apiUrl}/revision-sessions`, request, {
      context: this.localLoadingContext(),
    });
  }

  getSession(sessionId: number): Observable<RevisionSessionResponse> {
    return this.http.get<RevisionSessionResponse>(
      `${this.apiUrl}/revision-sessions/${sessionId}`,
      { context: this.localLoadingContext() },
    );
  }

  submitSession(
    sessionId: number,
    answers: RevisionSubmissionAnswer[],
  ): Observable<RevisionSessionResult> {
    const request: RevisionSubmissionRequest = { answers };
    return this.http.post<RevisionSessionResult>(
      `${this.apiUrl}/revision-sessions/${sessionId}/submit`,
      request,
      { context: this.localLoadingContext() },
    );
  }

  getResult(sessionId: number): Observable<RevisionSessionResult> {
    return this.http.get<RevisionSessionResult>(
      `${this.apiUrl}/revision-sessions/${sessionId}/result`,
      { context: this.localLoadingContext() },
    );
  }

  getHistory(options: {
    status?: RevisionStatus;
    limit?: number;
    offset?: number;
  } = {}): Observable<RevisionHistoryPage> {
    const params: Record<string, string> = {
      limit: String(options.limit ?? 10),
      offset: String(options.offset ?? 0),
    };
    if (options.status) params['status'] = options.status;
    return this.http.get<RevisionHistoryPage>(`${this.apiUrl}/revision-sessions`, {
      params,
      context: this.localLoadingContext(),
    });
  }

  getSmartReadiness(questionCount: number): Observable<SmartReadiness> {
    return this.http.get<SmartReadiness>(
      `${this.apiUrl}/revision-sessions/smart-readiness`,
      { params: { question_count: questionCount }, context: this.localLoadingContext() },
    );
  }

  private localLoadingContext(): HttpContext {
    return new HttpContext().set(SKIP_GLOBAL_LOADER, true);
  }
}

