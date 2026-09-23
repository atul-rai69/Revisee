import { isPlatformBrowser } from '@angular/common';
import { Component, HostBinding, PLATFORM_ID, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../../core/services/auth.service';
import { ToasterService } from '../../../../core/services/toaster.service';

interface PrimaryNavigationItem {
  readonly label: string;
  readonly icon: string;
  readonly route: string;
}

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
})
export class Sidebar {
  readonly navigation: readonly PrimaryNavigationItem[] = [
    { label: 'Home', icon: 'ph-house', route: '/app/dashboard' },
    { label: 'Library', icon: 'ph-books', route: '/app/library' },
    { label: 'Revise', icon: 'ph-pencil-line', route: '/app/revise' },
    { label: 'Topics', icon: 'ph-tag', route: '/app/labels' },
  ];
  readonly collapsed = signal(false);

  private readonly storageKey = 'revisee.sidebar.collapsed';
  private readonly platformId = inject(PLATFORM_ID);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly toaster = inject(ToasterService);

  @HostBinding('class.is-collapsed') get isCollapsed(): boolean { return this.collapsed(); }

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.collapsed.set(localStorage.getItem(this.storageKey) === 'true');
    }
  }

  toggleCollapsed(): void {
    this.collapsed.update((value) => !value);
    if (isPlatformBrowser(this.platformId)) {
      localStorage.setItem(this.storageKey, String(this.collapsed()));
    }
  }

  onLogout(): void {
    this.authService.logout().subscribe({
      next: () => {
        this.authService.clearToken();
        this.toaster.success('Logged out successfully.');
        void this.router.navigate(['/']);
      },
      error: () => this.toaster.error('Could not log out. Please try again.'),
    });
  }
}
