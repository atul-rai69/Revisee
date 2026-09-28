import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { TimeoutError, catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';


function isAuthenticationEndpoint(url: string): boolean {
  return ['/login', '/register', '/auth/refresh', '/auth/logout']
    .some((path) => url.endsWith(path));
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const toaster = inject(ToasterService);
  const authenticationEndpoint = isAuthenticationEndpoint(request.url);
  const token = auth.getToken();
  const authorizedRequest = token && !authenticationEndpoint
    ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : request;

  return next(authorizedRequest).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 403 && !authenticationEndpoint) {
        toaster.error('You do not have permission to perform this action.');
      }
      if (error.status === 0 && !authenticationEndpoint) {
        toaster.error('Unable to connect to the server.');
      }
      if (error.status >= 500 && !authenticationEndpoint) {
        toaster.error('Something went wrong on the server.');
      }

      if (error.status !== 401 || authenticationEndpoint) {
        return throwError(() => error);
      }

      const authCode = error.headers.get('X-Auth-Error');
      if (authCode !== 'access_token_expired' || !token) {
        endSession(auth, router, toaster, 'Your session is no longer valid. Please log in again.');
        return throwError(() => error);
      }

      return auth.refreshAccessToken().pipe(
        catchError((refreshError: unknown) => {
          const transient = refreshError instanceof TimeoutError || (
            refreshError instanceof HttpErrorResponse && (
              refreshError.status === 0 || refreshError.status >= 500
            )
          );
          const message = transient
            ? 'Your session could not be restored because the server is unavailable.'
            : 'Your session expired. Please log in again.';
          endSession(auth, router, toaster, message);
          return throwError(() => refreshError);
        }),
        switchMap(() => {
          const replacement = auth.getToken();
          if (!replacement) return throwError(() => error);
          return next(request.clone({
            setHeaders: { Authorization: `Bearer ${replacement}` },
          })).pipe(catchError((retryError: HttpErrorResponse) => {
            if (retryError.status === 401) {
              endSession(
                auth,
                router,
                toaster,
                'Your session is no longer valid. Please log in again.',
              );
            }
            return throwError(() => retryError);
          }));
        }),
      );
    }),
  );
};

function endSession(
  auth: AuthService,
  router: Router,
  toaster: ToasterService,
  message: string,
): void {
  if (!auth.invalidateSession()) return;
  toaster.warning(message);
  void router.navigate(['/']);
}
