import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';
import { AuthService, LoginResponse } from './auth.service';

const AUTHENTICATION: LoginResponse = {
  access_token: 'access-token',
  token_type: 'bearer',
  expires_in: 1800,
  user: { id: 7, username: 'atul', email: 'atul@example.test' },
};

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.setItem('token', 'legacy-persisted-token');
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('removes the legacy persisted token and keeps new access tokens in memory', () => {
    expect(localStorage.getItem('token')).toBeNull();
    service.setToken('memory-only');
    expect(service.getToken()).toBe('memory-only');
    expect(localStorage.getItem('token')).toBeNull();
    service.clearToken();
    expect(service.getToken()).toBeNull();
  });

  it('logs in with credentials and accepts the safe authentication response', () => {
    service.login('atul', 'secret').subscribe((response) => {
      expect(response.user.username).toBe('atul');
    });
    const request = http.expectOne(`${environment.apiUrl}/login`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ username: 'atul', password: 'secret' });
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.headers.get('X-Revisee-CSRF')).toBe('spa');
    expect(request.request.context.get(SKIP_GLOBAL_LOADER)).toBe(true);
    request.flush(AUTHENTICATION);
    expect(service.getToken()).toBe('access-token');
    expect(service.currentStatus()).toBe('authenticated');
  });

  it('registers with a JSON body and credentials', () => {
    service.register('new-user', 'new-user@example.test', 'safe-password').subscribe();
    const request = http.expectOne(`${environment.apiUrl}/register`);
    expect(request.request.body).toEqual({
      username: 'new-user',
      email: 'new-user@example.test',
      password: 'safe-password',
    });
    expect(request.request.withCredentials).toBe(true);
    request.flush({ ...AUTHENTICATION, message: 'Registration successful' });
  });

  it('uses one shared refresh request for simultaneous subscribers', () => {
    let completed = 0;
    service.refreshAccessToken().subscribe(() => completed += 1);
    service.refreshAccessToken().subscribe(() => completed += 1);
    const requests = http.match(`${environment.apiUrl}/auth/refresh`);
    expect(requests).toHaveLength(1);
    expect(requests[0].request.withCredentials).toBe(true);
    expect(requests[0].request.headers.get('X-Revisee-CSRF')).toBe('spa');
    requests[0].flush(AUTHENTICATION);
    expect(completed).toBe(2);
  });

  it('restores authentication on startup and finalizes an expected missing session', async () => {
    const restored = service.restoreSession();
    expect(service.currentStatus()).toBe('checking');
    http.expectOne(`${environment.apiUrl}/auth/refresh`).flush(AUTHENTICATION);
    await restored;
    expect(service.currentStatus()).toBe('authenticated');

    service.clearToken();
    const missing = service.restoreSession();
    http.expectOne(`${environment.apiUrl}/auth/refresh`).flush(
      { detail: 'Authentication required' },
      { status: 401, statusText: 'Unauthorized' },
    );
    await missing;
    expect(service.currentStatus()).toBe('unauthenticated');
  });

  it('logs out with credentials and clears browser authentication even on failure', () => {
    service.setToken('access-token');
    service.logout().subscribe();
    const successful = http.expectOne(`${environment.apiUrl}/auth/logout`);
    expect(successful.request.withCredentials).toBe(true);
    successful.flush({ message: 'Logged out successfully' });
    expect(service.getToken()).toBeNull();

    service.setToken('another-token');
    service.logout().subscribe({ error: () => undefined });
    http.expectOne(`${environment.apiUrl}/auth/logout`).flush(
      { detail: 'Unavailable' },
      { status: 503, statusText: 'Unavailable' },
    );
    expect(service.getToken()).toBeNull();
    expect(service.currentStatus()).toBe('unauthenticated');
  });
});
