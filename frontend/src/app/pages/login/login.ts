import { HttpErrorResponse } from '@angular/common/http';
import { Component, HostListener, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ToasterService } from '../../core/services/toaster.service';
import { RevealDirective } from '../../shared/directives/reveal.directive';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RevealDirective],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  readonly authMode = signal<'login' | 'register'>('login');
  readonly passwordVisible = signal(false);
  readonly submitting = signal(false);
  readonly loginError = signal<string | null>(null);
  readonly registrationError = signal<string | null>(null);
  readonly headerScrolled = signal(false);
  readonly form;
  readonly registrationForm;

  constructor(
    formBuilder: FormBuilder,
    private readonly authService: AuthService,
    private readonly router: Router,
    private readonly toaster: ToasterService,
  ) {
    this.form = formBuilder.nonNullable.group({
      username: ['', Validators.required],
      password: ['', Validators.required],
    });
    this.registrationForm = formBuilder.nonNullable.group({
      username: ['', [
        Validators.required,
        Validators.minLength(3),
        Validators.maxLength(100),
        Validators.pattern(/^[A-Za-z0-9][A-Za-z0-9_.-]*$/),
      ]],
      email: ['', [Validators.required, Validators.email, Validators.maxLength(100)]],
      password: ['', [Validators.required, Validators.minLength(8), Validators.maxLength(128)]],
      confirmPassword: ['', Validators.required],
    });
  }

  showLogin(): void {
    if (this.submitting()) return;
    this.authMode.set('login');
    this.registrationError.set(null);
    this.passwordVisible.set(false);
  }

  showRegistration(): void {
    if (this.submitting()) return;
    this.authMode.set('register');
    this.loginError.set(null);
    this.passwordVisible.set(false);
  }

  togglePasswordVisibility(): void {
    this.passwordVisible.update((visible) => !visible);
  }

  @HostListener('window:scroll')
  updateHeaderSurface(): void {
    this.headerScrolled.set(window.scrollY > 16);
  }

  onLogin(): void {
    if (this.submitting()) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.loginError.set('Enter your username and password to continue.');
      return;
    }

    const credentials = this.form.getRawValue();
    this.submitting.set(true);
    this.loginError.set(null);
    this.form.disable();

    this.authService
      .login(credentials.username, credentials.password)
      .pipe(
        finalize(() => {
          this.submitting.set(false);
          this.form.enable();
        }),
      )
      .subscribe({
        next: (response) => {
          this.authService.setToken(response.access_token);
          this.toaster.success('Welcome back to your learning space.', {
            title: 'Logged in',
          });
          void this.router.navigate(['/app']);
        },
        error: (error: HttpErrorResponse) => this.loginError.set(this.loginErrorMessage(error)),
      });
  }

  onRegister(): void {
    if (this.submitting()) return;
    const rawRegistration = this.registrationForm.getRawValue();
    this.registrationForm.patchValue({
      username: rawRegistration.username.trim(),
      email: rawRegistration.email.trim(),
    });
    const registration = this.registrationForm.getRawValue();
    if (this.registrationForm.invalid || registration.password !== registration.confirmPassword) {
      this.registrationForm.markAllAsTouched();
      this.registrationError.set(
        registration.password !== registration.confirmPassword
          ? 'Passwords do not match.'
          : 'Check the highlighted account details and try again.',
      );
      return;
    }

    this.submitting.set(true);
    this.registrationError.set(null);
    this.registrationForm.disable();

    this.authService
      .register(registration.username.trim(), registration.email.trim(), registration.password)
      .pipe(
        finalize(() => {
          this.submitting.set(false);
          this.registrationForm.enable();
        }),
      )
      .subscribe({
        next: (response) => {
          this.authService.setToken(response.access_token);
          this.toaster.success('Your Revisee account is ready.', {
            title: 'Account created',
          });
          void this.router.navigate(['/app']);
        },
        error: (error: HttpErrorResponse) => {
          this.registrationError.set(this.registrationErrorMessage(error));
        },
      });
  }

  passwordsDoNotMatch(): boolean {
    const { password, confirmPassword } = this.registrationForm.getRawValue();
    return this.registrationForm.controls.confirmPassword.touched
      && password !== confirmPassword;
  }

  private loginErrorMessage(error: HttpErrorResponse): string {
    if (error.status === 401) return 'Username or password is incorrect.';
    if (error.status === 0) return 'Revisee could not reach the server. Check your connection and try again.';
    if (error.status >= 500) return 'Revisee is temporarily unavailable. Please try again.';
    return 'Login could not be completed. Check your details and try again.';
  }

  private registrationErrorMessage(error: HttpErrorResponse): string {
    if (error.status === 400 || error.status === 409) {
      return 'An account with that username or email already exists.';
    }
    if (error.status === 422) return 'Check your username, email and password requirements.';
    if (error.status === 0) return 'Revisee could not reach the server. Check your connection and try again.';
    if (error.status >= 500) return 'Registration is temporarily unavailable. Please try again.';
    return 'Your account could not be created. Check your details and try again.';
  }
}
