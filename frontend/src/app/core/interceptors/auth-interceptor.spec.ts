import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { vi } from 'vitest';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';
import { authInterceptor } from './auth-interceptor';

class FakeRouter { navigate = vi.fn(); }

describe('authInterceptor', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let toaster: ToasterService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useClass: FakeRouter },
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
    toaster = TestBed.inject(ToasterService);
  });

  afterEach(() => http.verify());

  it('preserves bearer-token attachment', () => {
    auth.setToken('token');
    auth.logout().subscribe({ error: () => undefined });
    const request = http.expectOne(`${environment.apiUrl}/logout`);
    expect(request.request.headers.get('Authorization')).toBe('Bearer token');
    request.flush({ message: 'ok' });
  });

  it('leaves login network feedback to the login form rather than duplicating a toast', () => {
    const errorToast = vi.spyOn(toaster, 'error');
    auth.login('atul', 'secret').subscribe({ error: () => undefined });
    const request = http.expectOne(`${environment.apiUrl}/login`);
    request.error(new ProgressEvent('offline'), { status: 0 });
    expect(errorToast).not.toHaveBeenCalled();
  });

  it('leaves registration network feedback to the registration form', () => {
    const errorToast = vi.spyOn(toaster, 'error');
    auth.register('new-user', 'new-user@example.test', 'safe-password').subscribe({ error: () => undefined });
    const request = http.expectOne(`${environment.apiUrl}/register`);
    request.error(new ProgressEvent('offline'), { status: 0 });
    expect(errorToast).not.toHaveBeenCalled();
  });
});
