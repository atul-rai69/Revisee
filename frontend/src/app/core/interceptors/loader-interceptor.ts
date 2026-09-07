import { HttpContextToken, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { finalize } from 'rxjs';
import { LoaderService } from '../services/loader.service';

export const SKIP_GLOBAL_LOADER = new HttpContextToken<boolean>(() => false);

export const loaderInterceptor: HttpInterceptorFn = (req, next) => {
  const loader = inject(LoaderService);

  if (req.context.get(SKIP_GLOBAL_LOADER)) {
    return next(req);
  }

  // Count each request so parallel API calls keep the spinner visible.
  loader.show();

  return next(req).pipe(
    finalize(() => {
      // Always hide when the request completes, fails, or is cancelled.
      loader.hide();
    })
  );
};
