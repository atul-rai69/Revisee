import { TestBed } from '@angular/core/testing';
import { CanActivateFn, Router, UrlTree } from '@angular/router';
import { BehaviorSubject, Observable, filter, take } from 'rxjs';
import { vi } from 'vitest';
import { AuthService, AuthenticationStatus } from '../services/auth.service';
import { ToasterService } from '../services/toaster.service';
import { authGuard } from './auth-guard';

class FakeAuthService {
  readonly status = new BehaviorSubject<AuthenticationStatus>('checking');
  waitForInitialCheck() {
    return this.status.pipe(filter((value) => value !== 'checking'), take(1));
  }
}

class FakeRouter {
  createUrlTree = vi.fn(() => ({ redirected: true }) as unknown as UrlTree);
}

describe('authGuard', () => {
  const executeGuard: CanActivateFn = (...parameters) =>
    TestBed.runInInjectionContext(() => authGuard(...parameters));
  let auth: FakeAuthService;
  let router: FakeRouter;
  let toaster: ToasterService;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [
      { provide: AuthService, useClass: FakeAuthService },
      { provide: Router, useClass: FakeRouter },
      ToasterService,
    ] });
    auth = TestBed.inject(AuthService) as unknown as FakeAuthService;
    router = TestBed.inject(Router) as unknown as FakeRouter;
    toaster = TestBed.inject(ToasterService);
  });

  it('waits for restoration before allowing a protected route', () => {
    const values: Array<boolean | UrlTree> = [];
    (executeGuard({} as never, {} as never) as unknown as Observable<boolean | UrlTree>)
      .subscribe((value) => values.push(value));
    expect(values).toEqual([]);
    auth.status.next('authenticated');
    expect(values).toEqual([true]);
  });

  it('redirects after an expected missing or expired refresh session', () => {
    const warning = vi.spyOn(toaster, 'warning');
    let result: boolean | UrlTree | undefined;
    (executeGuard({} as never, {} as never) as unknown as Observable<boolean | UrlTree>)
      .subscribe((value) => result = value);
    auth.status.next('unauthenticated');
    expect(result).toBeTruthy();
    expect(router.createUrlTree).toHaveBeenCalledWith(['/']);
    expect(warning).toHaveBeenCalledWith('Please log in first.');
  });

  it('reports a recoverable restoration network failure separately', () => {
    const warning = vi.spyOn(toaster, 'warning');
    (executeGuard({} as never, {} as never) as unknown as Observable<boolean | UrlTree>)
      .subscribe();
    auth.status.next('error');
    expect(warning).toHaveBeenCalledWith(
      'Revisee could not restore your session. Check your connection and try again.',
    );
  });
});
