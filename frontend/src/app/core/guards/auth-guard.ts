import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';


export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  const auth = inject(AuthService);
  const toaster = inject(ToasterService);

  return auth.waitForInitialCheck().pipe(map((status) => {
    if (status === 'authenticated') return true;
    if (status === 'error') {
      toaster.warning('Revisee could not restore your session. Check your connection and try again.');
    } else {
      toaster.warning('Please log in first.');
    }
    return router.createUrlTree(['/']);
  }));
};
