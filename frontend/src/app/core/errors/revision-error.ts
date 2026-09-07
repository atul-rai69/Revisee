import { HttpErrorResponse } from '@angular/common/http';

export type RevisionErrorKind =
  | 'AUTHENTICATION'
  | 'SESSION_UNAVAILABLE'
  | 'INSUFFICIENT_QUESTIONS'
  | 'ALREADY_COMPLETED'
  | 'NOT_COMPLETED'
  | 'ANSWER_SET_MISMATCH'
  | 'VALIDATION'
  | 'NETWORK'
  | 'SERVER'
  | 'UNKNOWN';

export interface RevisionErrorMessage {
  kind: RevisionErrorKind;
  title: string;
  message: string;
  retryable: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function detailCode(error: HttpErrorResponse): string | null {
  if (!isRecord(error.error)) return null;
  const detail = error.error['detail'];
  if (!isRecord(detail)) return null;
  const code = detail['code'];
  return typeof code === 'string' ? code : null;
}

export function mapRevisionError(error: HttpErrorResponse): RevisionErrorMessage {
  const code = detailCode(error);

  if (error.status === 401) {
    return { kind: 'AUTHENTICATION', title: 'Session expired', message: 'Please sign in again to continue.', retryable: false };
  }
  if (error.status === 404) {
    return { kind: 'SESSION_UNAVAILABLE', title: 'Session unavailable', message: 'It may have been removed or may not belong to you.', retryable: false };
  }
  if (error.status === 409 && code === 'INSUFFICIENT_QUESTION_BANK') {
    return { kind: 'INSUFFICIENT_QUESTIONS', title: 'Not enough questions', message: 'Choose fewer questions or different Topics and try again.', retryable: false };
  }
  if (error.status === 409 && code === 'REVISION_SESSION_ALREADY_COMPLETED') {
    return { kind: 'ALREADY_COMPLETED', title: 'Revision already submitted', message: 'Your completed result is ready to view.', retryable: false };
  }
  if (error.status === 409 && code === 'REVISION_SESSION_NOT_COMPLETED') {
    return { kind: 'NOT_COMPLETED', title: 'Revision still in progress', message: 'Complete the revision before opening its results.', retryable: false };
  }
  if (error.status === 422 && code === 'ANSWER_SET_MISMATCH') {
    return { kind: 'ANSWER_SET_MISMATCH', title: 'Answers do not match this revision', message: 'Reload the session and complete every question before retrying.', retryable: true };
  }
  if (error.status === 422) {
    return { kind: 'VALIDATION', title: 'Check your revision choices', message: 'Some submitted values were not accepted. Review them and try again.', retryable: false };
  }
  if (error.status === 0) {
    return { kind: 'NETWORK', title: 'Connection problem', message: 'Revisee could not reach the server. Check your connection and retry.', retryable: true };
  }
  if (error.status >= 500) {
    return { kind: 'SERVER', title: 'Revision unavailable', message: 'Something went wrong while preparing your revision. Try again.', retryable: true };
  }
  return { kind: 'UNKNOWN', title: 'Revision unavailable', message: 'The request could not be completed. Try again.', retryable: true };
}

