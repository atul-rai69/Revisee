import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export interface DashboardSummary {
  login_streak: number;
  total_items: number;
  total_labels: number;
  username: string;
}

export interface LearningItemsSummary {
  id: number;
  title: string;
  description_text: string | null;
  labels: string | null;
  first_image_url: string | null;
  image_count: number;
  pdf_count: number;
  hours_ago: number;
}

export interface LearningItemsSummaryResponse {
  message: string;
  data: LearningItemsSummary[];
}

@Injectable({
  providedIn: 'root',
})
export class DashboardService {
  private apiUrl = environment.apiUrl;
  
  constructor(
    private http: HttpClient
  ) {}
  
  getDashboardSummary(options: { localLoading?: boolean } = {}): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(
      `${this.apiUrl}/dashboard/summary`,
      { context: this.requestContext(options.localLoading) },
    );
  }

  getLearningItemSummary(options: { localLoading?: boolean } = {}): Observable<LearningItemsSummaryResponse> {
    return this.http.get<LearningItemsSummaryResponse>(
      `${this.apiUrl}/dashboard/learning-items-summary`,
      { context: this.requestContext(options.localLoading) },
    );
  }

  private requestContext(localLoading = false): HttpContext {
    return localLoading
      ? new HttpContext().set(SKIP_GLOBAL_LOADER, true)
      : new HttpContext();
  }
}
