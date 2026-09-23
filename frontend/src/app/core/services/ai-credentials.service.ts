import { HttpClient, HttpContext } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export type AICredentialStatus = 'VALID' | 'INVALID';
export type GenerationSource = 'REVISEE' | 'PERSONAL';

export interface AICredentialUsage {
  request_count: number;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  updated_at: string | null;
}

export interface AICredential {
  id: number;
  provider: 'GEMINI';
  name: string;
  masked_identifier: string;
  status: AICredentialStatus;
  is_default: boolean;
  last_validated_at: string;
  last_used_at: string | null;
  created_at: string;
  usage: AICredentialUsage;
}

export interface AICredentialListResponse {
  credentials: AICredential[];
  provider_console_url: string;
  quota_remaining_available: false;
}

export interface AICredentialCreateRequest {
  provider: 'GEMINI';
  name: string;
  api_key: string;
  make_default: boolean;
}

export interface AICredentialUpdateRequest {
  name?: string;
  api_key?: string;
  make_default?: boolean;
}

export interface GenerationChoice {
  generation_source: GenerationSource;
  credential_id: number | null;
  personal_remarks: string | null;
}

@Injectable({ providedIn: 'root' })
export class AICredentialsService {
  private readonly apiUrl = environment.apiUrl;
  private readonly localContext = new HttpContext().set(SKIP_GLOBAL_LOADER, true);

  constructor(private readonly http: HttpClient) {}

  list(): Observable<AICredentialListResponse> {
    return this.http.get<AICredentialListResponse>(`${this.apiUrl}/ai-credentials`, {
      context: this.localContext,
    });
  }

  create(request: AICredentialCreateRequest): Observable<AICredential> {
    return this.http.post<AICredential>(`${this.apiUrl}/ai-credentials`, request, {
      context: this.localContext,
    });
  }

  update(id: number, request: AICredentialUpdateRequest): Observable<AICredential> {
    return this.http.patch<AICredential>(`${this.apiUrl}/ai-credentials/${id}`, request, {
      context: this.localContext,
    });
  }

  setDefault(id: number): Observable<AICredential> {
    return this.http.put<AICredential>(
      `${this.apiUrl}/ai-credentials/${id}/default`,
      {},
      { context: this.localContext },
    );
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/ai-credentials/${id}`, {
      context: this.localContext,
    });
  }
}
