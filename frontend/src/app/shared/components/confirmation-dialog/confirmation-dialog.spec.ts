import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ConfirmationDialog } from './confirmation-dialog';

describe('ConfirmationDialog', () => {
  let fixture: ComponentFixture<ConfirmationDialog>;
  let component: ConfirmationDialog;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [ConfirmationDialog] }).compileComponents();
    fixture = TestBed.createComponent(ConfirmationDialog);
    component = fixture.componentInstance;
    component.title = 'Submit?';
    component.message = 'Answers cannot be changed.';
    fixture.detectChanges();
  });

  it('supports keyboard cancellation and blocks dismissal while busy', () => {
    let cancellations = 0;
    component.cancelled.subscribe(() => cancellations += 1);
    component.handleKeyboard(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(cancellations).toBe(1);
    component.busy = true;
    component.handleKeyboard(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(cancellations).toBe(1);
  });

  it('emits final confirmation only once per explicit action', () => {
    let confirmations = 0;
    component.confirmed.subscribe(() => confirmations += 1);
    component.confirm();
    expect(confirmations).toBe(1);
  });
});
