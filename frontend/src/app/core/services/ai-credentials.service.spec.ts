import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { AICredentialsService } from './ai-credentials.service';

describe('AICredentialsService', () => {
  let service: AICredentialsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [AICredentialsService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AICredentialsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('never sends a saved key while listing credentials', () => {
    service.list().subscribe();
    const request = http.expectOne(`${environment.apiUrl}/ai-credentials`);
    expect(request.request.method).toBe('GET');
    expect(request.request.body).toBeNull();
    request.flush({ credentials: [], provider_console_url: 'https://aistudio.google.com/usage', quota_remaining_available: false });
  });

  it('uses the authenticated JSON contracts for create, default and delete', () => {
    service.create({ provider: 'GEMINI', name: 'Study key', api_key: 'secret-value', make_default: true }).subscribe();
    const create = http.expectOne(`${environment.apiUrl}/ai-credentials`);
    expect(create.request.method).toBe('POST');
    expect(create.request.body.api_key).toBe('secret-value');
    create.flush({});

    service.setDefault(7).subscribe();
    expect(http.expectOne(`${environment.apiUrl}/ai-credentials/7/default`).request.method).toBe('PUT');

    service.delete(7).subscribe();
    expect(http.expectOne(`${environment.apiUrl}/ai-credentials/7`).request.method).toBe('DELETE');
  });
});
