import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';
import { mapRevisionError, RevisionErrorMessage } from '../../core/errors/revision-error';
import {
  AnswerOption,
  CompletedRevisionQuestion,
  RevisionSessionResult,
} from '../../core/models/revision.models';
import { RevisionSessionService } from '../../core/services/revision-session.service';

@Component({
  selector: 'app-revision-result',
  imports: [CommonModule],
  templateUrl: './revision-result.html',
  styleUrl: './revision-result.css',
})
export class RevisionResult implements OnInit {
  readonly result = signal<RevisionSessionResult | null>(null);
  readonly loading = signal(false);
  readonly loadError = signal<RevisionErrorMessage | null>(null);
  private sessionId = 0;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly revisionService: RevisionSessionService,
  ) {}

  ngOnInit(): void {
    this.sessionId = Number(this.route.snapshot.paramMap.get('sessionId'));
    if (!Number.isInteger(this.sessionId) || this.sessionId <= 0) {
      this.loading.set(false);
      this.loadError.set({
        kind: 'SESSION_UNAVAILABLE',
        title: 'Session unavailable',
        message: 'This result link is not valid.',
        retryable: false,
      });
      return;
    }
    this.loadResult();
  }

  loadResult(): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.loadError.set(null);
    this.revisionService
      .getResult(this.sessionId)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (result) => this.result.set(result),
        error: (error: HttpErrorResponse) => {
          const mapped = mapRevisionError(error);
          if (mapped.kind === 'NOT_COMPLETED') {
            void this.router.navigate(['/app/revision-sessions', this.sessionId], {
              replaceUrl: true,
            });
            return;
          }
          this.loadError.set(mapped);
        },
      });
  }

  optionText(question: CompletedRevisionQuestion, option: AnswerOption): string {
    return question.options.find((candidate) => candidate.label === option)?.text ?? option;
  }

  formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
  }

  scrollToReview(): void {
    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    document.getElementById('question-review')?.scrollIntoView({
      behavior: reducedMotion ? 'auto' : 'smooth',
    });
  }

  startAnother(): void {
    void this.router.navigate(['/app/revise']);
  }
}
