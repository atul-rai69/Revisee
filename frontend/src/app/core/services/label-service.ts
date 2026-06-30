import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Label{
  id: number;
  user_id: number;
  label_name: string;
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

  getLabels(): Observable<Label[]> {
    return this.http.get<Label[]>(
      `${this.apiUrl}/labels`
    );
  }

  createLabel(
    label_name: string
  ): Observable<any> {
    return this.http.post(
      `${this.apiUrl}/labels`,
      {
        label_name
      }
    );
  }

  updateLabel(
    id: number,
    label_name: string
  ): Observable<any> {
    return this.http.patch(
      `${this.apiUrl}/labels`,
      {
        id,
        label_name
      }
    );
  }

}
