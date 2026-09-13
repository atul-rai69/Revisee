import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { SystemState } from '../../shared/components/system-state/system-state';

@Component({
  selector: 'app-not-found',
  imports: [SystemState],
  templateUrl: './not-found.html',
  styleUrl: './not-found.css',
})
export class NotFound {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  goHome(): void {
    void this.router.navigate([this.auth.isLoggedIn() ? '/app/dashboard' : '/']);
  }
}
