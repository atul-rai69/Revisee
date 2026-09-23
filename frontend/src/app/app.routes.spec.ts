import { routes } from './app.routes';

describe('application revision routes', () => {
  it('keeps product routes under the guarded application shell', () => {
    const appRoute = routes.find((route) => route.path === 'app');
    expect(appRoute?.canActivate?.length).toBeGreaterThan(0);
    const childPaths = appRoute?.children?.map((route) => route.path);
    expect(childPaths).toContain('revise');
    expect(childPaths).toContain('revision-sessions/:sessionId');
    expect(childPaths).toContain('revision-sessions/:sessionId/result');
    expect(childPaths).toContain('revision-sessions');
    expect(childPaths).toContain('analytics');
    expect(childPaths).toContain('settings');
    expect(childPaths).toContain('learning-items/:id/questions');
    expect(childPaths).toContain('library');
    expect(childPaths).not.toContain('playground');
    expect(childPaths).not.toContain('canvas');
  });

  it('redirects /app to Home and provides shell and global not-found routes', () => {
    const appRoute = routes.find((route) => route.path === 'app');
    const redirect = appRoute?.children?.find((route) => route.path === '');
    expect(redirect?.redirectTo).toBe('dashboard');
    expect(appRoute?.children?.at(-1)?.path).toBe('**');
    expect(routes.at(-1)?.path).toBe('**');
  });

  it('exposes verified completed-session results without a roadmap-only route gate', () => {
    const appRoute = routes.find((route) => route.path === 'app');
    const resultsRoute = appRoute?.children?.find((route) => route.path?.endsWith('/result'));
    expect(resultsRoute?.canMatch).toBeUndefined();
  });
});
