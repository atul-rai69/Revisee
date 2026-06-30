import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const toaster = inject(ToasterService);

  // Attach the token to every API request when the user is logged in.
  const token = authService.getToken();
  const authRequest = token
    ? req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    })
    : req;

  return next(authRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      const isLoginRequest = req.url.includes('/login');

      // 401 means the backend rejected the token or session.
      if (error.status === 401 && !isLoginRequest) {
        authService.clearToken();
        toaster.warning('Your session expired. Please login again.');
        router.navigate(['/']);
      }

      // 403 means the user is logged in but lacks permission.
      if (error.status === 403) {
        toaster.error('You do not have permission to perform this action.');
      }

      // Status 0 usually means the backend is unreachable.
      if (error.status === 0) {
        toaster.error('Unable to connect to the server.');
      }

      // 5xx errors are server-side failures.
      if (error.status >= 500) {
        toaster.error('Something went wrong on the server.');
      }

      return throwError(() => error);
    })
  );
};
