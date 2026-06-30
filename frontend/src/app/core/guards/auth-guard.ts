import { CanActivateFn } from '@angular/router';
import { Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';


export const authGuard: CanActivateFn = (route, state) => {
  const router = inject(Router);
  const authService = inject(AuthService);
  const toaster = inject(ToasterService);

  // Check if a saved token exists before opening protected pages.
  const token = authService.getToken();

  if (!token) {
    toaster.warning('Please login first.');

    return router.createUrlTree(['/']);
  }

  // Clear expired tokens so the next request starts fresh.
  if (authService.isTokenExpired(token)) {
    authService.clearToken();
    toaster.warning('Your session expired. Please login again.');

    return router.createUrlTree(['/']);
  }

  // Token exists and is still valid, so the route can load.
  return true;
};
