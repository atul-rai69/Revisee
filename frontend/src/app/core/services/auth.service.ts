import { HttpClient, HttpContext, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, TimeoutError, catchError, filter, finalize, firstValueFrom, shareReplay, take, tap, throwError, timeout } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export type AuthenticationStatus = 'checking' | 'authenticated' | 'unauthenticated' | 'error';

export interface AuthenticatedUser {
  id: number;
  username: string;
  email: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthenticatedUser;
}

export interface RegistrationResponse extends LoginResponse { message: string; }
export interface LogoutResponse { message: string; }

const CSRF_HEADERS = new HttpHeaders({ 'X-Revisee-CSRF': 'spa' });
const REFRESH_TIMEOUT_MS = 15_000;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly apiUrl = environment.apiUrl;
  private accessToken: string | null = null;
  private refreshInFlight: Observable<LoginResponse> | null = null;
  private redirectHandled = false;
  private readonly statusSubject = new BehaviorSubject<AuthenticationStatus>('checking');
  private readonly userSubject = new BehaviorSubject<AuthenticatedUser | null>(null);

  readonly status$ = this.statusSubject.asObservable();
  readonly user$ = this.userSubject.asObservable();

  constructor(private readonly http: HttpClient) {
    // Remove the legacy persisted access token. Refresh credentials are cookie-only.
    try { localStorage.removeItem('token'); } catch { /* Storage may be unavailable. */ }
  }

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(
      `${this.apiUrl}/login`,
      { username, password },
      this.authRequestOptions(),
    ).pipe(tap((response) => this.acceptAuthentication(response)));
  }

  register(username: string, email: string, password: string): Observable<RegistrationResponse> {
    return this.http.post<RegistrationResponse>(
      `${this.apiUrl}/register`,
      { username, email, password },
      this.authRequestOptions(),
    ).pipe(tap((response) => this.acceptAuthentication(response)));
  }

  refreshAccessToken(): Observable<LoginResponse> {
    if (this.refreshInFlight) return this.refreshInFlight;
    this.refreshInFlight = this.http.post<LoginResponse>(
      `${this.apiUrl}/auth/refresh`,
      {},
      this.authRequestOptions(),
    ).pipe(
      timeout(REFRESH_TIMEOUT_MS),
      tap((response) => this.acceptAuthentication(response)),
      catchError((error: unknown) => {
        this.accessToken = null;
        this.userSubject.next(null);
        this.statusSubject.next(this.isTransientRefreshFailure(error) ? 'error' : 'unauthenticated');
        return throwError(() => error);
      }),
      finalize(() => { this.refreshInFlight = null; }),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.refreshInFlight;
  }

  async restoreSession(): Promise<void> {
    this.statusSubject.next('checking');
    try {
      await firstValueFrom(this.refreshAccessToken());
    } catch {
      // Missing/expired cookies and transient failures are represented by status.
    }
  }

  logout(): Observable<LogoutResponse> {
    return this.http.post<LogoutResponse>(
      `${this.apiUrl}/auth/logout`,
      {},
      this.authRequestOptions(),
    ).pipe(finalize(() => this.clearAuthentication()));
  }

  getToken(): string | null { return this.accessToken; }

  setToken(token: string): void {
    this.accessToken = token;
    this.statusSubject.next('authenticated');
    this.redirectHandled = false;
  }

  clearToken(): void { this.clearAuthentication(); }

  isLoggedIn(): boolean {
    return this.statusSubject.value === 'authenticated' && this.accessToken !== null;
  }

  currentStatus(): AuthenticationStatus { return this.statusSubject.value; }

  waitForInitialCheck(): Observable<AuthenticationStatus> {
    return this.status$.pipe(filter((status) => status !== 'checking'), take(1));
  }

  invalidateSession(): boolean {
    const shouldNotify = !this.redirectHandled;
    this.redirectHandled = true;
    this.clearAuthentication(false);
    return shouldNotify;
  }

  private acceptAuthentication(response: LoginResponse): void {
    this.accessToken = response.access_token;
    this.userSubject.next(response.user);
    this.statusSubject.next('authenticated');
    this.redirectHandled = false;
  }

  private clearAuthentication(resetRedirect = true): void {
    this.accessToken = null;
    this.userSubject.next(null);
    this.statusSubject.next('unauthenticated');
    if (resetRedirect) this.redirectHandled = false;
  }

  private authRequestOptions(): {
    withCredentials: true;
    headers: HttpHeaders;
    context: HttpContext;
  } {
    return {
      withCredentials: true,
      headers: CSRF_HEADERS,
      context: new HttpContext().set(SKIP_GLOBAL_LOADER, true),
    };
  }

  private isTransientRefreshFailure(error: unknown): boolean {
    return error instanceof TimeoutError || (
      error instanceof HttpErrorResponse && (error.status === 0 || error.status >= 500)
    );
  }
}
