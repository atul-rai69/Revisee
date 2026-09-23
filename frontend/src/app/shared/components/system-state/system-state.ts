import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-system-state',
  templateUrl: './system-state.html',
  styleUrl: './system-state.css',
})
export class SystemState {
  @Input({ required: true }) title = '';
  @Input({ required: true }) message = '';
  @Input() icon = 'ph-notebook';
  @Input() actionLabel = '';
  @Input() role: 'status' | 'alert' = 'status';
  @Output() readonly action = new EventEmitter<void>();
}
