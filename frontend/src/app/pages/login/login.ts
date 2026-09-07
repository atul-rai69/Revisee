import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ToasterService } from '../../core/services/toaster.service';
import { KnowledgeParticles } from '../../shared/components/knowledge-particles/knowledge-particles';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, KnowledgeParticles],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  readonly passwordVisible = signal(false);
  readonly submitting = signal(false);
  readonly loginError = signal<string | null>(null);
  readonly form;

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
  }

  togglePasswordVisibility(): void {
    this.passwordVisible.update((visible) => !visible);
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
          void this.router.navigate(['/app/dashboard']);
        },
        error: (error: HttpErrorResponse) => this.loginError.set(this.loginErrorMessage(error)),
      });
  }

  private loginErrorMessage(error: HttpErrorResponse): string {
    if (error.status === 401) return 'Username or password is incorrect.';
    if (error.status === 0) return 'Revisee could not reach the server. Check your connection and try again.';
    if (error.status >= 500) return 'Revisee is temporarily unavailable. Please try again.';
    return 'Login could not be completed. Check your details and try again.';
  }
}
