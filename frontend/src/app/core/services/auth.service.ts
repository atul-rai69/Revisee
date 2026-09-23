import { Injectable } from '@angular/core';
import { HttpClient, HttpContext } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegistrationResponse extends LoginResponse {
  message: string;
}

export interface LogoutResponse {
  message: string;
}

interface JwtPayload {
  exp?: number;
  [key: string]: unknown;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private apiUrl = environment.apiUrl;
  private readonly tokenKey = 'token';

  constructor(private http: HttpClient) {}

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(
      `${this.apiUrl}/login`,
      { username, password },
      { context: new HttpContext().set(SKIP_GLOBAL_LOADER, true) },
    );
  }

  register(username: string, email: string, password: string): Observable<RegistrationResponse> {
    return this.http.post<RegistrationResponse>(
      `${this.apiUrl}/register`,
      { username, email, password },
      { context: new HttpContext().set(SKIP_GLOBAL_LOADER, true) },
    );
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  setToken(token: string): void {
    localStorage.setItem(this.tokenKey, token);
  }

  clearToken(): void {
    localStorage.removeItem(this.tokenKey);
  }

  logout(): Observable<LogoutResponse> {
    return this.http.post<LogoutResponse>(
      `${this.apiUrl}/logout`,
      {}
    );
  }

  isLoggedIn(): boolean {
    const token = this.getToken();

    return !!token && !this.isTokenExpired(token);
  }

  isTokenExpired(token: string): boolean {
    const payload = this.decodeJwtPayload(token);

    // Tokens without an expiry are left for the backend to validate.
    if (!payload?.exp) {
      return false;
    }

    const expiryTime = payload.exp * 1000;

    return Date.now() >= expiryTime;
  }

  private decodeJwtPayload(token: string): JwtPayload | null {
    const parts = token.split('.');

    // Non-JWT tokens cannot be decoded on the client.
    if (parts.length !== 3) {
      return null;
    }

    try {
      const base64 = parts[1]
        .replace(/-/g, '+')
        .replace(/_/g, '/');

      const payload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((char) => `%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`)
          .join('')
      );

      return JSON.parse(payload);
    } catch {
      // Malformed JWTs should not be trusted.
      return {
        exp: 0,
      };
    }
  }
}
