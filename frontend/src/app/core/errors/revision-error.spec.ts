import { HttpErrorResponse } from '@angular/common/http';
import { mapRevisionError } from './revision-error';

describe('mapRevisionError', () => {
  it('maps known backend states without exposing raw payloads', () => {
    const insufficient = new HttpErrorResponse({ status: 409, error: { detail: { code: 'INSUFFICIENT_QUESTION_BANK', secret: 'hidden' } } });
    const unavailable = new HttpErrorResponse({ status: 404, error: { detail: 'database detail' } });
    const mismatch = new HttpErrorResponse({ status: 422, error: { detail: { code: 'ANSWER_SET_MISMATCH' } } });

    expect(mapRevisionError(insufficient).kind).toBe('INSUFFICIENT_QUESTIONS');
    expect(mapRevisionError(unavailable).message).toContain('may not belong to you');
    expect(mapRevisionError(mismatch).kind).toBe('ANSWER_SET_MISMATCH');
    expect(JSON.stringify(mapRevisionError(insufficient))).not.toContain('secret');
  });

  it('maps network, authentication, and server failures', () => {
    expect(mapRevisionError(new HttpErrorResponse({ status: 0 })).kind).toBe('NETWORK');
    expect(mapRevisionError(new HttpErrorResponse({ status: 401 })).kind).toBe('AUTHENTICATION');
    expect(mapRevisionError(new HttpErrorResponse({ status: 503 })).retryable).toBe(true);
  });
});
