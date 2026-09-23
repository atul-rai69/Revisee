import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Observable, of, Subject } from 'rxjs';
import { vi } from 'vitest';
import {
  AICredential,
  AICredentialListResponse,
  AICredentialsService,
} from '../../core/services/ai-credentials.service';
import { ToasterService } from '../../core/services/toaster.service';
import { Settings } from './settings';

const credential: AICredential = {
  id: 4,
  provider: 'GEMINI',
  name: 'Study key',
  masked_identifier: '•••• 1234',
  status: 'VALID',
  is_default: true,
  last_validated_at: '2026-09-15T10:00:00Z',
  last_used_at: null,
  created_at: '2026-09-15T10:00:00Z',
  usage: { request_count: 0, input_tokens: null, output_tokens: null, total_tokens: null, updated_at: null },
};

class FakeCredentialsService {
  listResult: Observable<AICredentialListResponse> = of({
    credentials: [credential],
    provider_console_url: 'https://aistudio.google.com/usage',
    quota_remaining_available: false,
  });
  createResult: Observable<AICredential> = of(credential);
  create = vi.fn(() => this.createResult);
  list = vi.fn(() => this.listResult);
  update = vi.fn(() => of(credential));
  setDefault = vi.fn(() => of(credential));
  delete = vi.fn(() => of(undefined));
}

describe('Settings', () => {
  let fixture: ComponentFixture<Settings>;
  let component: Settings;
  let service: FakeCredentialsService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Settings],
      providers: [
        ToasterService,
        { provide: AICredentialsService, useClass: FakeCredentialsService },
      ],
    }).compileComponents();
    service = TestBed.inject(AICredentialsService) as unknown as FakeCredentialsService;
    fixture = TestBed.createComponent(Settings);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renders only the masked identifier and honest quota language', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('•••• 1234');
    expect(text).toContain('Remaining quota: Not available');
    expect(text).not.toContain('tokens left');
  });

  it('prevents duplicate credential submissions while validation is pending', () => {
    const pending = new Subject<AICredential>();
    service.createResult = pending.asObservable();
    component.createForm.setValue({ name: 'Second', apiKey: 'complete-test-key', makeDefault: false });
    component.addCredential();
    component.addCredential();
    expect(service.create).toHaveBeenCalledTimes(1);
    expect(component.creating()).toBe(true);
  });

  it('clears the replacement key field after a successful rotation', () => {
    component.beginReplace(credential);
    component.editForm.setValue({ name: 'Rotated', apiKey: 'replacement-test-key' });
    component.replaceCredential(credential.id);
    expect(service.update).toHaveBeenCalledWith(credential.id, {
      name: 'Rotated', api_key: 'replacement-test-key',
    });
    expect(component.editForm.controls.apiKey.value).toBe('');
  });
});
