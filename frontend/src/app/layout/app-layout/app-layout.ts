import { Component, HostListener, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { ToasterService } from '../../core/services/toaster.service';
import { Sidebar } from '../../shared/components/sidebar/sidebar/sidebar';

@Component({
  selector: 'app-app-layout',
  imports: [Sidebar, RouterLink, RouterOutlet],
  templateUrl: './app-layout.html',
  styleUrl: './app-layout.css',
})
export class AppLayout {
  readonly pageTitle = signal('Home');
  readonly focusedMode = signal(false);
  readonly accountMenuOpen = signal(false);

  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly toaster = inject(ToasterService);

  constructor() {
    this.updateShell(this.router.url);
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      takeUntilDestroyed(),
    ).subscribe((event) => {
      this.accountMenuOpen.set(false);
      this.updateShell(event.urlAfterRedirects);
    });
  }

  toggleAccountMenu(): void {
    this.accountMenuOpen.update((open) => !open);
  }

  @HostListener('document:keydown.escape')
  closeAccountMenu(): void {
    this.accountMenuOpen.set(false);
  }

  onLogout(): void {
    this.auth.logout().subscribe({
      next: () => {
        this.auth.clearToken();
        this.toaster.success('Logged out successfully.');
        void this.router.navigate(['/']);
      },
      error: () => this.toaster.error('Could not log out. Please try again.'),
    });
  }

  private updateShell(url: string): void {
    const path = url.split(/[?#]/)[0];
    this.focusedMode.set(/^\/app\/revision-sessions\/[^/]+$/.test(path));
    const routes: readonly [RegExp, string][] = [
      [/\/app\/library$/, 'Library'],
      [/\/app\/labels$/, 'Topics'],
      [/\/app\/new-item$/, 'Add learning material'],
      [/\/questions$/, 'Question bank'],
      [/\/revision-sessions\/[^/]+\/result$/, 'Revision result'],
      [/\/app\/revision-sessions$/, 'Revision history'],
      [/\/app\/analytics$/, 'Mastery analytics'],
      [/\/app\/settings$/, 'Settings'],
      [/\/app\/revise$/, 'Revise'],
      [/\/learning-items\//, 'Learning item'],
      [/\/app\/dashboard$/, 'Home'],
    ];
    this.pageTitle.set(routes.find(([pattern]) => pattern.test(path))?.[1] ?? 'Revisee');
  }
}
