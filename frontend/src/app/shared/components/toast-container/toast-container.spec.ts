import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ToasterService } from '../../../core/services/toaster.service';
import { ToastContainer } from './toast-container';

describe('ToastContainer', () => {
  let fixture: ComponentFixture<ToastContainer>;
  let toaster: ToasterService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ToastContainer] }).compileComponents();
    fixture = TestBed.createComponent(ToastContainer);
    toaster = TestBed.inject(ToasterService);
  });

  afterEach(() => toaster.clear());

  it('uses alert semantics for errors and polite status semantics for other variants', () => {
    toaster.error('Submission failed', { duration: 0 });
    toaster.info('Revision resumed', { duration: 0 });
    fixture.detectChanges();
    const messages = fixture.nativeElement.querySelectorAll('.toast-message') as NodeListOf<HTMLElement>;
    expect(messages[0].getAttribute('role')).toBe('status');
    expect(messages[0].getAttribute('aria-live')).toBe('polite');
    expect(messages[1].getAttribute('role')).toBe('alert');
    expect(messages[1].getAttribute('aria-live')).toBe('assertive');
  });
});
