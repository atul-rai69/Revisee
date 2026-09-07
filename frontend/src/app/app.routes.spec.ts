import { routes } from './app.routes';

describe('application revision routes', () => {
  it('keeps revision routes under the guarded application shell', () => {
    const appRoute = routes.find((route) => route.path === 'app');
    expect(appRoute?.canActivate?.length).toBeGreaterThan(0);
    const childPaths = appRoute?.children?.map((route) => route.path);
    expect(childPaths).toContain('revise');
    expect(childPaths).toContain('revision-sessions/:sessionId');
    expect(childPaths).toContain('revision-sessions/:sessionId/result');
    expect(childPaths).toContain('learning-items/:id/questions');
  });
});
