import { HttpClient, HttpErrorResponse, HttpHeaders, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { vi } from 'vitest';
import { environment } from '../../../environments/environment';
import { AuthService, LoginResponse } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';
import { authInterceptor } from './auth-interceptor';

class FakeRouter { navigate = vi.fn(); }

const REFRESHED: LoginResponse = {
  access_token: 'replacement-token',
  token_type: 'bearer',
  expires_in: 1800,
  user: { id: 1, username: 'atul', email: 'atul@example.test' },
};

const EXPIRED_HEADERS = new HttpHeaders({ 'X-Auth-Error': 'access_token_expired' });

describe('authInterceptor', () => {
  let auth: AuthService;
  let client: HttpClient;
  let http: HttpTestingController;
  let router: FakeRouter;
  let toaster: ToasterService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useClass: FakeRouter },
        ToasterService,
      ],
    });
    auth = TestBed.inject(AuthService);
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router) as unknown as FakeRouter;
    toaster = TestBed.inject(ToasterService);
  });

  afterEach(() => http.verify());

  it('attaches the in-memory bearer token to protected API calls', () => {
    auth.setToken('access-token');
    client.get(`${environment.apiUrl}/labels`).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/labels`);
    expect(request.request.headers.get('Authorization')).toBe('Bearer access-token');
    request.flush([]);
  });

  it('refreshes an expired access token and retries the original request once', () => {
    auth.setToken('expired-token');
    let result: unknown;
    client.get(`${environment.apiUrl}/labels`).subscribe((value) => result = value);
    http.expectOne(`${environment.apiUrl}/labels`).flush(
      { detail: 'Authentication required' },
      { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    const refresh = http.expectOne(`${environment.apiUrl}/auth/refresh`);
    expect(refresh.request.headers.has('Authorization')).toBe(false);
    expect(refresh.request.withCredentials).toBe(true);
    refresh.flush(REFRESHED);
    const retry = http.expectOne(`${environment.apiUrl}/labels`);
    expect(retry.request.headers.get('Authorization')).toBe('Bearer replacement-token');
    retry.flush([{ id: 1 }]);
    expect(result).toEqual([{ id: 1 }]);
  });

  it('uses one refresh for simultaneous expired requests', () => {
    auth.setToken('expired-token');
    client.get(`${environment.apiUrl}/labels`).subscribe();
    client.get(`${environment.apiUrl}/dashboard/summary`).subscribe();
    http.expectOne(`${environment.apiUrl}/labels`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    http.expectOne(`${environment.apiUrl}/dashboard/summary`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    const refreshRequests = http.match(`${environment.apiUrl}/auth/refresh`);
    expect(refreshRequests).toHaveLength(1);
    refreshRequests[0].flush(REFRESHED);
    http.expectOne(`${environment.apiUrl}/labels`).flush([]);
    http.expectOne(`${environment.apiUrl}/dashboard/summary`).flush({});
  });

  it('retries only once and does not loop when the replacement is rejected', () => {
    auth.setToken('expired-token');
    let finalStatus: number | undefined;
    client.get(`${environment.apiUrl}/labels`).subscribe({
      error: (error: HttpErrorResponse) => finalStatus = error.status,
    });
    http.expectOne(`${environment.apiUrl}/labels`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    http.expectOne(`${environment.apiUrl}/auth/refresh`).flush(REFRESHED);
    http.expectOne(`${environment.apiUrl}/labels`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    expect(finalStatus).toBe(401);
    expect(auth.getToken()).toBeNull();
    expect(router.navigate).toHaveBeenCalledTimes(1);
    http.expectNone(`${environment.apiUrl}/auth/refresh`);
  });

  it('clears and redirects once when a shared refresh fails', () => {
    auth.setToken('expired-token');
    const warning = vi.spyOn(toaster, 'warning');
    const errors: HttpErrorResponse[] = [];
    client.get(`${environment.apiUrl}/labels`).subscribe({ error: (error) => errors.push(error) });
    client.get(`${environment.apiUrl}/dashboard/summary`).subscribe({
      error: (error) => errors.push(error),
    });
    http.expectOne(`${environment.apiUrl}/labels`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    http.expectOne(`${environment.apiUrl}/dashboard/summary`).flush(
      {}, { status: 401, statusText: 'Unauthorized', headers: EXPIRED_HEADERS },
    );
    http.expectOne(`${environment.apiUrl}/auth/refresh`).flush(
      {}, { status: 401, statusText: 'Unauthorized' },
    );
    expect(errors).toHaveLength(2);
    expect(auth.getToken()).toBeNull();
    expect(router.navigate).toHaveBeenCalledTimes(1);
    expect(warning).toHaveBeenCalledTimes(1);
    http.expectNone(`${environment.apiUrl}/auth/refresh`);
  });

  it('does not refresh login failures or add bearer authentication to auth endpoints', () => {
    auth.setToken('existing-token');
    const errorToast = vi.spyOn(toaster, 'error');
    auth.login('atul', 'wrong').subscribe({ error: () => undefined });
    const login = http.expectOne(`${environment.apiUrl}/login`);
    expect(login.request.headers.has('Authorization')).toBe(false);
    login.flush({}, { status: 401, statusText: 'Unauthorized' });
    http.expectNone(`${environment.apiUrl}/auth/refresh`);
    expect(errorToast).not.toHaveBeenCalled();
  });

  it('does not restore immediately after manual logout', () => {
    auth.setToken('access-token');
    auth.logout().subscribe();
    const logout = http.expectOne(`${environment.apiUrl}/auth/logout`);
    expect(logout.request.headers.has('Authorization')).toBe(false);
    expect(logout.request.withCredentials).toBe(true);
    logout.flush({ message: 'Logged out successfully' });
    expect(auth.currentStatus()).toBe('unauthenticated');
    http.expectNone(`${environment.apiUrl}/auth/refresh`);
  });
});
