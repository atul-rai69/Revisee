import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { AuthService, LoginResponse } from '../../core/services/auth.service';
import { ToasterService } from '../../core/services/toaster.service';
import { Login } from './login';

class FakeAuthService {
  result: Observable<LoginResponse> = of({ access_token: 'token', token_type: 'bearer' });
  calls = 0;
  credentials: { username: string; password: string } | null = null;
  setToken = vi.fn();
  login(username: string, password: string): Observable<LoginResponse> {
    this.calls += 1;
    this.credentials = { username, password };
    return this.result;
  }
}

class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('Login', () => {
  let component: Login;
  let fixture: ComponentFixture<Login>;
  let auth: FakeAuthService;
  let toaster: ToasterService;

  beforeEach(async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [
        ToasterService,
        { provide: AuthService, useClass: FakeAuthService },
        { provide: Router, useClass: FakeRouter },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(Login);
    component = fixture.componentInstance;
    auth = TestBed.inject(AuthService) as unknown as FakeAuthService;
    toaster = TestBed.inject(ToasterService);
    fixture.detectChanges();
  });

  afterEach(() => vi.restoreAllMocks());

  function submit(username = 'atul', password = 'secret'): void {
    component.form.setValue({ username, password });
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    fixture.detectChanges();
  }

  it('requires both real backend-supported fields', () => {
    component.onLogin();
    fixture.detectChanges();
    expect(auth.calls).toBe(0);
    expect(fixture.nativeElement.textContent).toContain('Username is required.');
    expect(fixture.nativeElement.textContent).toContain('Password is required.');
  });

  it('toggles password visibility with an accessible button name', () => {
    const input = fixture.nativeElement.querySelector('#password') as HTMLInputElement;
    const toggle = fixture.nativeElement.querySelector('.password-toggle') as HTMLButtonElement;
    expect(input.type).toBe('password');
    expect(toggle.getAttribute('aria-label')).toBe('Show password');
    toggle.click();
    fixture.detectChanges();
    expect(input.type).toBe('text');
    expect(toggle.getAttribute('aria-label')).toBe('Hide password');
  });

  it('submits the unchanged contract, stores the token, and navigates', () => {
    const success = vi.spyOn(toaster, 'success');
    submit();
    expect(auth.credentials).toEqual({ username: 'atul', password: 'secret' });
    expect(auth.setToken).toHaveBeenCalledWith('token');
    expect(success).toHaveBeenCalled();
    expect((TestBed.inject(Router) as unknown as FakeRouter).navigate).toHaveBeenCalledWith(['/app/dashboard']);
  });

  it('shows safe invalid-credential and network feedback', () => {
    auth.result = throwError(() => new HttpErrorResponse({ status: 401 }));
    submit();
    expect(component.loginError()).toBe('Username or password is incorrect.');
    auth.result = throwError(() => new HttpErrorResponse({ status: 0 }));
    submit();
    expect(component.loginError()).toContain('Check your connection');
  });

  it('uses a local loading state and prevents duplicate requests', () => {
    auth.result = new Subject<LoginResponse>();
    submit();
    component.onLogin();
    fixture.detectChanges();
    expect(auth.calls).toBe(1);
    expect(component.submitting()).toBe(true);
    expect((fixture.nativeElement.querySelector('.login-button') as HTMLButtonElement).disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Logging in...');
  });

  it('contains no unsupported account actions and works without canvas support', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).not.toContain('Forgot Password');
    expect(text).not.toContain('Remember Me');
    expect(text).not.toContain('Sign up');
    expect(component).toBeTruthy();
  });
});
