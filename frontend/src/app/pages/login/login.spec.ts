import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, Subject, of, throwError } from 'rxjs';
import { vi } from 'vitest';
import {
  AuthService,
  LoginResponse,
  RegistrationResponse,
} from '../../core/services/auth.service';
import { ToasterService } from '../../core/services/toaster.service';
import { Login } from './login';

class FakeAuthService {
  result: Observable<LoginResponse> = of({ access_token: 'token', token_type: 'bearer' });
  registrationResult: Observable<RegistrationResponse> = of({
    access_token: 'registration-token',
    token_type: 'bearer',
    message: 'Registration successful',
  });
  calls = 0;
  registrationCalls = 0;
  credentials: { username: string; password: string } | null = null;
  registration: { username: string; email: string; password: string } | null = null;
  setToken = vi.fn();

  login(username: string, password: string): Observable<LoginResponse> {
    this.calls += 1;
    this.credentials = { username, password };
    return this.result;
  }

  register(username: string, email: string, password: string): Observable<RegistrationResponse> {
    this.registrationCalls += 1;
    this.registration = { username, email, password };
    return this.registrationResult;
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

  function submitLogin(username = 'atul', password = 'secret'): void {
    component.form.setValue({ username, password });
    component.onLogin();
    fixture.detectChanges();
  }

  function submitRegistration(overrides: Partial<{
    username: string;
    email: string;
    password: string;
    confirmPassword: string;
  }> = {}): void {
    component.showRegistration();
    component.registrationForm.setValue({
      username: 'new-user',
      email: 'new-user@example.test',
      password: 'safe-password',
      confirmPassword: 'safe-password',
      ...overrides,
    });
    component.onRegister();
    fixture.detectChanges();
  }

  it('requires both real backend-supported login fields', () => {
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

  it('submits login, stores the token, and navigates', () => {
    const success = vi.spyOn(toaster, 'success');
    submitLogin();
    expect(auth.credentials).toEqual({ username: 'atul', password: 'secret' });
    expect(auth.setToken).toHaveBeenCalledWith('token');
    expect(success).toHaveBeenCalled();
    expect((TestBed.inject(Router) as unknown as FakeRouter).navigate).toHaveBeenCalledWith(['/app']);
  });

  it('shows safe invalid-credential and network feedback', () => {
    auth.result = throwError(() => new HttpErrorResponse({ status: 401 }));
    submitLogin();
    expect(component.loginError()).toBe('Username or password is incorrect.');
    auth.result = throwError(() => new HttpErrorResponse({ status: 0 }));
    submitLogin();
    expect(component.loginError()).toContain('Check your connection');
  });

  it('switches to an accessible registration form from the landing page', () => {
    component.showRegistration();
    fixture.detectChanges();
    expect(component.authMode()).toBe('register');
    expect(fixture.nativeElement.querySelector('#register-email')).toBeTruthy();
    expect(fixture.nativeElement.textContent).toContain('Create your Revisee account.');
  });

  it('validates registration fields and matching passwords before sending', () => {
    submitRegistration({ username: 'x', email: 'bad', password: 'short', confirmPassword: 'other' });
    expect(auth.registrationCalls).toBe(0);
    expect(component.registrationError()).toBe('Passwords do not match.');
    expect(fixture.nativeElement.textContent).toContain('Enter a valid email address.');
  });

  it('registers with the JSON-backed contract, stores the token, and enters the app', () => {
    const success = vi.spyOn(toaster, 'success');
    submitRegistration({ username: '  new-user  ', email: '  New@Example.test  ' });
    expect(auth.registration).toEqual({
      username: 'new-user',
      email: 'New@Example.test',
      password: 'safe-password',
    });
    expect(auth.setToken).toHaveBeenCalledWith('registration-token');
    expect(success).toHaveBeenCalledWith('Your Revisee account is ready.', { title: 'Account created' });
    expect((TestBed.inject(Router) as unknown as FakeRouter).navigate).toHaveBeenCalledWith(['/app']);
  });

  it('shows duplicate-account feedback locally', () => {
    auth.registrationResult = throwError(() => new HttpErrorResponse({ status: 400 }));
    submitRegistration();
    expect(component.registrationError()).toContain('username or email already exists');
  });

  it('prevents duplicate registration requests while one is pending', () => {
    auth.registrationResult = new Subject<RegistrationResponse>();
    submitRegistration();
    component.onRegister();
    fixture.detectChanges();
    expect(auth.registrationCalls).toBe(1);
    expect(component.submitting()).toBe(true);
    expect((fixture.nativeElement.querySelector('.login-button') as HTMLButtonElement).disabled).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Creating account...');
  });

  it('keeps unsupported recovery actions absent and uses the approved brand', () => {
    const element = fixture.nativeElement as HTMLElement;
    const text = element.textContent ?? '';
    expect(text).not.toContain('Forgot Password');
    expect(text).not.toContain('Remember Me');
    expect(element.querySelector('img[src*="revisee-logo-primary.svg"]')).toBeTruthy();
    expect(text).toContain('Living Study Notes');
    expect(text).toContain('Create account');
  });
});
