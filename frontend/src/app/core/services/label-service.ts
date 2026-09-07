import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export interface Label{
  id: number;
  user_id: number;
  label_name: string;
}

export interface LabelMutationResponse {
  message: string;
  label: Label;
}

@Injectable({
  providedIn: 'root',
})
export class LabelService {
  
  private apiUrl =
    environment.apiUrl;

  constructor(
    private http: HttpClient
  ) {}

  getLabels(options: { localLoading?: boolean } = {}): Observable<Label[]> {
    return this.http.get<Label[]>(
      `${this.apiUrl}/labels`,
      {
        context: options.localLoading
          ? new HttpContext().set(SKIP_GLOBAL_LOADER, true)
          : new HttpContext(),
      }
    );
  }

  createLabel(
    label_name: string
  ): Observable<LabelMutationResponse> {
    return this.http.post<LabelMutationResponse>(
      `${this.apiUrl}/labels`,
      {
        label_name
      }
    );
  }

  updateLabel(
    id: number,
    label_name: string
  ): Observable<LabelMutationResponse> {
    return this.http.patch<LabelMutationResponse>(
      `${this.apiUrl}/labels`,
      {
        id,
        label_name
      }
    );
  }

}
