import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';


export interface LearningItem {
  id: number;
  title: string;
  description_text: string;
  created_at: string;
  updated_at: string;
  labels: string;
  image_urls: string;
  pdf_urls: string;
  image_count: number;
  pdf_count: number;
  theory: string | null;
  first_image_url: string;
  hours_ago: number;
}

export interface ApiResponse {
  message: string;
  data: LearningItem;
}


@Injectable({
  providedIn: 'root',
})
export class LearningItem {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  createLearningItem(
    formData: FormData
  ): Observable<any> {

    return this.http.post(

      `${this.apiUrl}/learning-items`,

      formData
    );
  }


  getLearningItem(itemId: number): Observable<ApiResponse> {
    return this.http.get<ApiResponse>(
      `${this.apiUrl}/learning-item/${itemId}`,
      {}
    );
  }

  getAicontent(title: string, description: string):Observable<any>{
    return this.http.post(
      `${this.apiUrl}/generate`,
      {
        title,
        description
      }
    );
  }

  deleteLearningItem(
    id : number 
  ): Observable<any> {

    return this.http.delete(
      `${this.apiUrl}/learning-items`,
      {
        body: { id }
      }
    );
  }
}
