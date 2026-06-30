import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface DashboardSummary {
  login_streak: number;
  total_items: number;
  total_labels: number;
  username: string;
}

export interface LearningItemsSummary {
  id: number;
  title: string;
  description_text: string;
  labels: string;
  first_image_url: string;
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
  
  getDashboardSummary(): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(
      `${this.apiUrl}/dashboard/summary`
    );
  }

  getLearningItemSummary(): Observable<LearningItemsSummaryResponse> {
    return this.http.get<LearningItemsSummaryResponse>(
      `${this.apiUrl}/dashboard/learning-items-summary`
    );
  }
}
