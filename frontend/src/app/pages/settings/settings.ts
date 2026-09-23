import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import {
  AICredential,
  AICredentialsService,
} from '../../core/services/ai-credentials.service';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-settings',
  imports: [DatePipe, ReactiveFormsModule],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class Settings implements OnInit {
  readonly credentials = signal<AICredential[]>([]);
  readonly providerConsoleUrl = signal('https://aistudio.google.com/usage');
  readonly loading = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly creating = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly savingId = signal<number | null>(null);
  readonly deletingId = signal<number | null>(null);
  readonly pendingDeleteId = signal<number | null>(null);
  readonly formError = signal<string | null>(null);
  readonly editError = signal<string | null>(null);
  readonly createForm;
  readonly editForm;

  constructor(
    formBuilder: FormBuilder,
    private readonly credentialService: AICredentialsService,
    private readonly toaster: ToasterService,
  ) {
    this.createForm = formBuilder.nonNullable.group({
      name: ['', [Validators.required, Validators.maxLength(80)]],
      apiKey: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
      makeDefault: [false],
    });
    this.editForm = formBuilder.nonNullable.group({
      name: ['', [Validators.required, Validators.maxLength(80)]],
      apiKey: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
    });
  }

  ngOnInit(): void {
    this.loadCredentials();
  }

  loadCredentials(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.loadError.set(null);
    this.credentialService.list().pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (response) => {
        this.credentials.set(response.credentials);
        this.providerConsoleUrl.set(response.provider_console_url);
      },
      error: (error: HttpErrorResponse) => {
        this.loadError.set(error.status === 503
          ? 'Personal credential encryption is not configured on this server.'
          : 'Your Gemini credentials could not be loaded.');
      },
    });
  }

  addCredential(): void {
    if (this.creating()) return;
    this.createForm.markAllAsTouched();
    const value = this.createForm.getRawValue();
    if (this.createForm.invalid || !value.name.trim() || !value.apiKey.trim()) {
      this.formError.set('Enter a name and a valid Gemini API key.');
      return;
    }
    this.creating.set(true);
    this.formError.set(null);
    this.credentialService.create({
      provider: 'GEMINI',
      name: value.name.trim(),
      api_key: value.apiKey.trim(),
      make_default: value.makeDefault,
    }).pipe(finalize(() => this.creating.set(false))).subscribe({
      next: () => {
        this.createForm.reset({ name: '', apiKey: '', makeDefault: false });
        this.toaster.success('Gemini credential validated and encrypted.', { title: 'Credential saved' });
        this.loadCredentials();
      },
      error: (error: HttpErrorResponse) => this.formError.set(this.errorMessage(error)),
    });
  }

  beginReplace(credential: AICredential): void {
    this.editingId.set(credential.id);
    this.editError.set(null);
    this.editForm.reset({ name: credential.name, apiKey: '' });
  }

  cancelReplace(): void {
    if (this.savingId() === null) {
      this.editingId.set(null);
      this.editError.set(null);
    }
  }

  replaceCredential(id: number): void {
    if (this.savingId() !== null) return;
    this.editForm.markAllAsTouched();
    const value = this.editForm.getRawValue();
    if (this.editForm.invalid || !value.name.trim() || !value.apiKey.trim()) {
      this.editError.set('Enter a name and the complete replacement key.');
      return;
    }
    this.savingId.set(id);
    this.editError.set(null);
    this.credentialService.update(id, {
      name: value.name.trim(),
      api_key: value.apiKey.trim(),
    }).pipe(finalize(() => this.savingId.set(null))).subscribe({
      next: () => {
        this.editingId.set(null);
        this.editForm.reset({ name: '', apiKey: '' });
        this.toaster.success('The replacement key was validated and encrypted.');
        this.loadCredentials();
      },
      error: (error: HttpErrorResponse) => this.editError.set(this.errorMessage(error)),
    });
  }

  setDefault(id: number): void {
    if (this.savingId() !== null) return;
    this.savingId.set(id);
    this.credentialService.setDefault(id).pipe(finalize(() => this.savingId.set(null))).subscribe({
      next: () => {
        this.toaster.success('Default Gemini credential updated.');
        this.loadCredentials();
      },
      error: () => this.toaster.error('The default credential could not be changed.'),
    });
  }

  requestDelete(id: number): void {
    this.pendingDeleteId.set(id);
  }

  cancelDelete(): void {
    if (this.deletingId() === null) this.pendingDeleteId.set(null);
  }

  deleteCredential(id: number): void {
    if (this.deletingId() !== null) return;
    this.deletingId.set(id);
    this.credentialService.delete(id).pipe(finalize(() => this.deletingId.set(null))).subscribe({
      next: () => {
        this.pendingDeleteId.set(null);
        this.toaster.success('Gemini credential deleted.');
        this.loadCredentials();
      },
      error: () => this.toaster.error('The credential could not be deleted.'),
    });
  }

  usageLabel(credential: AICredential): string {
    return credential.usage.total_tokens === null
      ? 'Not available'
      : `${credential.usage.total_tokens.toLocaleString()} tokens`;
  }

  private errorMessage(error: HttpErrorResponse): string {
    if (error.status === 422) return 'Gemini rejected this key. Check that it is active and permitted to use the configured model.';
    if (error.status === 409 || error.status === 400) return 'A credential with this name or key already exists.';
    if (error.status === 429) return 'Gemini is rate limited. Wait briefly and try validating again.';
    if (error.status === 503) return 'Personal credential encryption or Gemini is temporarily unavailable.';
    return 'The credential could not be saved. Try again.';
  }
}
