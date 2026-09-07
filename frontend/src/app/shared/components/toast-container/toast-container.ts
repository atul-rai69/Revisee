import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { Toast, ToasterService } from '../../../core/services/toaster.service';

@Component({
  selector: 'app-toast-container',
  imports: [
    CommonModule
  ],
  templateUrl: './toast-container.html',
  styleUrl: './toast-container.css',
})
export class ToastContainer {
  readonly toaster = inject(ToasterService);

  getIcon(type: Toast['type']): string {
    const icons: Record<Toast['type'], string> = {
      success: 'ph-check-circle',
      error: 'ph-warning-circle',
      warning: 'ph-warning',
      info: 'ph-info',
    };

    return icons[type];
  }

  getTitle(toast: Toast): string {
    if (toast.title) {
      return toast.title;
    }

    const titles: Record<Toast['type'], string> = {
      success: 'Success',
      error: 'Error',
      warning: 'Warning',
      info: 'Info',
    };

    return titles[toast.type];
  }

  getRole(type: Toast['type']): 'alert' | 'status' {
    return type === 'error' ? 'alert' : 'status';
  }

  getAriaLive(type: Toast['type']): 'assertive' | 'polite' {
    return type === 'error' ? 'assertive' : 'polite';
  }
}
