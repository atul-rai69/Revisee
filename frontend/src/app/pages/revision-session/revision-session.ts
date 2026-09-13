import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';
import { mapRevisionError, RevisionErrorMessage } from '../../core/errors/revision-error';
import {
  AnswerOption,
  AnswerSafeRevisionQuestion,
  RevisionSessionResponse,
  RevisionSubmissionAnswer,
} from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { ToasterService } from '../../core/services/toaster.service';
import { ConfirmationDialog } from '../../shared/components/confirmation-dialog/confirmation-dialog';
import { environment } from '../../../environments/environment';

interface DraftAnswer {
  selectedOption: AnswerOption;
  timeTakenSeconds: number;
}

@Component({
  selector: 'app-revision-session',
  imports: [CommonModule, ConfirmationDialog],
  templateUrl: './revision-session.html',
  styleUrl: './revision-session.css',
})
export class RevisionSession implements OnInit, OnDestroy {
  readonly completedResultsEnabled = environment.features.phase3Results;
  readonly session = signal<RevisionSessionResponse | null>(null);
  readonly loading = signal(false);
  readonly loadError = signal<RevisionErrorMessage | null>(null);
  readonly submitError = signal<RevisionErrorMessage | null>(null);
  readonly submitting = signal(false);
  readonly currentIndex = signal(0);
  readonly showExitDialog = signal(false);
  readonly showSubmitDialog = signal(false);
  readonly elapsedSeconds = signal(0);

  private readonly answers = new Map<number, DraftAnswer>();
  private readonly questionTimes = new Map<number, number>();
  private sessionId = 0;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly revisionService: RevisionSessionService,
    private readonly toaster: ToasterService,
  ) {}

  ngOnInit(): void {
    this.sessionId = Number(this.route.snapshot.paramMap.get('sessionId'));
    if (!Number.isInteger(this.sessionId) || this.sessionId <= 0) {
      this.loading.set(false);
      this.loadError.set({
        kind: 'SESSION_UNAVAILABLE',
        title: 'Session unavailable',
        message: 'This revision link is not valid.',
        retryable: false,
      });
      return;
    }
    this.loadSession();
  }

  ngOnDestroy(): void {
    this.stopTimer();
  }

  @HostListener('window:beforeunload', ['$event'])
  warnBeforeLeaving(event: BeforeUnloadEvent): void {
    if (this.answers.size > 0 && !this.submitting()) {
      event.preventDefault();
    }
  }

  get currentQuestion(): AnswerSafeRevisionQuestion | null {
    return this.session()?.questions[this.currentIndex()] ?? null;
  }

  get answeredCount(): number {
    return this.answers.size;
  }

  get allAnswered(): boolean {
    const currentSession = this.session();
    return Boolean(currentSession && currentSession.questions.length === this.answers.size);
  }

  get topicSummary(): string {
    const labels = this.session()?.labels;
    return labels?.length ? labels.map((label) => label.label_name).join(', ') : 'All saved material';
  }

  loadSession(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.loadError.set(null);
    this.revisionService
      .getSession(this.sessionId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (session) => {
          if (session.status === 'COMPLETED') {
            if (this.completedResultsEnabled) {
              void this.router.navigate(['/app/revision-sessions', this.sessionId, 'result'], {
                replaceUrl: true,
              });
            } else {
              this.loadError.set({
                kind: 'ALREADY_COMPLETED',
                title: 'Revision already completed',
                message: 'Completed-session results are not available in this release.',
                retryable: false,
              });
            }
            return;
          }
          this.session.set(session);
          this.startTimer();
          this.toaster.info('Your saved question order has been restored.', {
            title: 'Revision resumed',
          });
        },
        error: (error: HttpErrorResponse) => this.loadError.set(mapRevisionError(error)),
      });
  }

  selectOption(option: AnswerOption): void {
    const question = this.currentQuestion;
    if (!question || this.submitting()) return;
    this.answers.set(question.session_question_id, {
      selectedOption: option,
      timeTakenSeconds: this.questionTimes.get(question.session_question_id) ?? 0,
    });
    this.submitError.set(null);
  }

  selectedOption(questionId: number): AnswerOption | null {
    return this.answers.get(questionId)?.selectedOption ?? null;
  }

  isAnswered(questionId: number): boolean {
    return this.answers.has(questionId);
  }

  goToQuestion(index: number): void {
    const questions = this.session()?.questions ?? [];
    if (index >= 0 && index < questions.length) this.currentIndex.set(index);
  }

  previous(): void {
    this.goToQuestion(this.currentIndex() - 1);
  }

  next(): void {
    this.goToQuestion(this.currentIndex() + 1);
  }

  requestExit(): void {
    if (this.answers.size === 0) {
      void this.router.navigate(['/app/revise']);
      return;
    }
    this.showExitDialog.set(true);
  }

  confirmExit(): void {
    this.showExitDialog.set(false);
    this.toaster.info('This session remains available, but unsubmitted answers were not saved.', {
      title: 'Continue later',
    });
    void this.router.navigate(['/app/revise']);
  }

  requestSubmission(): void {
    if (!this.completedResultsEnabled) {
      this.toaster.info('Completed-session results are not available in this release.');
      return;
    }
    if (!this.allAnswered) {
      this.toaster.warning('Choose one answer for every question before submitting.', {
        title: 'Complete every question',
      });
      return;
    }
    this.showSubmitDialog.set(true);
  }

  confirmSubmission(): void {
    const currentSession = this.session();
    if (!currentSession || !this.allAnswered || this.submitting()) return;

    const payload: RevisionSubmissionAnswer[] = currentSession.questions.map((question) => {
      const answer = this.answers.get(question.session_question_id)!;
      return {
        session_question_id: question.session_question_id,
        selected_option: answer.selectedOption,
        time_taken_seconds: answer.timeTakenSeconds,
      };
    });

    this.submitting.set(true);
    this.submitError.set(null);
    this.revisionService
      .submitSession(this.sessionId, payload)
      .pipe(
        finalize(() => {
          this.submitting.set(false);
          this.showSubmitDialog.set(false);
        }),
      )
      .subscribe({
        next: () => {
          this.stopTimer();
          this.toaster.success('Your results have been calculated.', {
            title: 'Revision submitted',
          });
          void this.router.navigate(['/app/revision-sessions', this.sessionId, 'result']);
        },
        error: (error: HttpErrorResponse) => {
          const mapped = mapRevisionError(error);
          if (mapped.kind === 'ALREADY_COMPLETED') {
            void this.router.navigate(['/app/revision-sessions', this.sessionId, 'result']);
            return;
          }
          this.submitError.set(mapped);
          this.toaster.error('Your answers were not submitted. You can retry safely.', {
            title: 'Submission failed',
          });
        },
      });
  }

  difficultyLabel(value: number): string {
    return value === 1 ? 'Easy' : value === 2 ? 'Medium' : 'Hard';
  }

  formatTime(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
  }

  private startTimer(): void {
    if (this.timer) return;
    this.timer = setInterval(() => {
      this.elapsedSeconds.update((value) => value + 1);
      const question = this.currentQuestion;
      if (!question) return;
      const nextTime = Math.min(
        3600,
        (this.questionTimes.get(question.session_question_id) ?? 0) + 1,
      );
      this.questionTimes.set(question.session_question_id, nextTime);
      const existing = this.answers.get(question.session_question_id);
      if (existing) {
        this.answers.set(question.session_question_id, {
          ...existing,
          timeTakenSeconds: nextTime,
        });
      }
    }, 1000);
  }

  private stopTimer(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
