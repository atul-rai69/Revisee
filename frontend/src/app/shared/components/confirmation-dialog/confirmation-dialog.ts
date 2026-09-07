import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnDestroy,
  Output,
  ViewChild,
} from '@angular/core';

@Component({
  selector: 'app-confirmation-dialog',
  templateUrl: './confirmation-dialog.html',
  styleUrl: './confirmation-dialog.css',
})
export class ConfirmationDialog implements AfterViewInit, OnDestroy {
  @Input({ required: true }) title = '';
  @Input({ required: true }) message = '';
  @Input() confirmLabel = 'Confirm';
  @Input() cancelLabel = 'Cancel';
  @Input() busy = false;
  @Input() tone: 'primary' | 'warning' = 'primary';

  @Output() readonly confirmed = new EventEmitter<void>();
  @Output() readonly cancelled = new EventEmitter<void>();

  @ViewChild('dialog', { static: true }) dialog!: ElementRef<HTMLElement>;

  private readonly previouslyFocused = document.activeElement as HTMLElement | null;

  ngAfterViewInit(): void {
    this.dialog.nativeElement.querySelector<HTMLElement>('button')?.focus();
  }

  ngOnDestroy(): void {
    this.previouslyFocused?.focus();
  }

  cancel(): void {
    if (!this.busy) this.cancelled.emit();
  }

  confirm(): void {
    if (!this.busy) this.confirmed.emit();
  }

  @HostListener('document:keydown', ['$event'])
  handleKeyboard(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.cancel();
      return;
    }
    if (event.key !== 'Tab') return;

    const buttons = Array.from(
      this.dialog.nativeElement.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'),
    );
    if (buttons.length === 0) return;
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

