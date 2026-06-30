import { Component } from '@angular/core';
import { RouterLink,RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../../core/services/auth.service';
import { Router } from '@angular/router';
import { ToasterService } from '../../../../core/services/toaster.service';

@Component({
  selector: 'app-sidebar',
  imports: [
    RouterLink,
    RouterLinkActive
  ],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  constructor(
    private authService: AuthService,
    private router: Router,
    private toaster: ToasterService
  ) {}

  onLogout(): void {
    this.authService.logout().subscribe({
      next: () => {
        this.authService.clearToken();
        this.toaster.success(
          'Logged out successfully'
        );
        this.router.navigate(['']);
      },
      error: (error) => {
        console.error(error);
        this.toaster.error('Could not log out. Please try again.');
      }
    });
  }
}
