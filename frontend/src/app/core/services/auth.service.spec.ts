import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('preserves the username/password login contract and requests local loading', () => {
    service.login('atul', 'secret').subscribe((response) => expect(response.access_token).toBe('token'));
    const request = http.expectOne(`${environment.apiUrl}/login`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ username: 'atul', password: 'secret' });
    expect(request.request.context.get(SKIP_GLOBAL_LOADER)).toBe(true);
    request.flush({ access_token: 'token', token_type: 'bearer' });
  });

  it('stores and clears the existing token key', () => {
    service.setToken('abc');
    expect(localStorage.getItem('token')).toBe('abc');
    service.clearToken();
    expect(localStorage.getItem('token')).toBeNull();
  });
});
