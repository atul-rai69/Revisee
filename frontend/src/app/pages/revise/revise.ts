import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';
import { mapRevisionError, RevisionErrorMessage } from '../../core/errors/revision-error';
import {
  LabelRevisionRequest,
  RandomRevisionRequest,
  RevisionSessionCreateRequest,
  RevisionStrategy,
  SmartRevisionRequest,
} from '../../core/models/revision.models';
import { Label, LabelService } from '../../core/services/label-service';
import { RevisionSessionService } from '../../core/services/revision-session.service';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-revise',
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './revise.html',
  styleUrl: './revise.css',
})
export class Revise implements OnInit {
  readonly topics = signal<Label[]>([]);
  readonly selectedTopicIds = signal<Set<number>>(new Set());
  readonly topicsLoading = signal(false);
  readonly creating = signal(false);
  readonly topicError = signal<string | null>(null);
  readonly createError = signal<RevisionErrorMessage | null>(null);

  readonly form;

  constructor(
    formBuilder: FormBuilder,
    private readonly labelService: LabelService,
    private readonly revisionService: RevisionSessionService,
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly toaster: ToasterService,
  ) {
    this.form = formBuilder.nonNullable.group({
      strategy: ['RANDOM' as RevisionStrategy, Validators.required],
      questionCount: [10, [Validators.required, Validators.min(1), Validators.max(50)]],
      questionsPerLabel: [5, [Validators.required, Validators.min(1), Validators.max(20)]],
      topicSearch: [''],
    });
  }

  ngOnInit(): void {
    const requestedStrategy = this.route.snapshot.queryParamMap.get('strategy');
    if (requestedStrategy === 'RANDOM' || requestedStrategy === 'LABEL' || requestedStrategy === 'SMART') {
      this.form.controls.strategy.setValue(requestedStrategy);
    }
    this.loadTopics();
  }

  get strategy(): RevisionStrategy {
    return this.form.controls.strategy.value;
  }

  get derivedQuestionCount(): number {
    return this.selectedTopicIds().size * this.form.controls.questionsPerLabel.value;
  }

  get canCreate(): boolean {
    if (this.creating()) return false;
    if (this.strategy === 'LABEL') {
      return (
        this.form.controls.questionsPerLabel.valid &&
        this.selectedTopicIds().size > 0 &&
        this.derivedQuestionCount <= 50
      );
    }
    return this.form.controls.questionCount.valid;
  }

  filteredTopics(): Label[] {
    const query = this.form.controls.topicSearch.value.trim().toLocaleLowerCase();
    return query
      ? this.topics().filter((topic) => topic.label_name.toLocaleLowerCase().includes(query))
      : this.topics();
  }

  selectStrategy(strategy: RevisionStrategy): void {
    this.form.controls.strategy.setValue(strategy);
    this.createError.set(null);
  }

  adjustQuestionCount(change: number): void {
    const control = this.form.controls.questionCount;
    control.setValue(Math.min(50, Math.max(1, control.value + change)));
  }

  adjustQuestionsPerLabel(change: number): void {
    const control = this.form.controls.questionsPerLabel;
    control.setValue(Math.min(20, Math.max(1, control.value + change)));
  }

  toggleTopic(topicId: number): void {
    this.selectedTopicIds.update((current) => {
      const next = new Set(current);
      if (next.has(topicId)) next.delete(topicId);
      else if (next.size < 10) next.add(topicId);
      return next;
    });
    this.createError.set(null);
  }

  isTopicSelected(topicId: number): boolean {
    return this.selectedTopicIds().has(topicId);
  }

  loadTopics(): void {
    if (this.topicsLoading()) return;
    this.topicsLoading.set(true);
    this.topicError.set(null);
    this.labelService
      .getLabels({ localLoading: true })
      .pipe(finalize(() => this.topicsLoading.set(false)))
      .subscribe({
        next: (topics) => this.topics.set(topics),
        error: () => this.topicError.set('Topics could not be loaded. Try again.'),
      });
  }

  startRevision(): void {
    if (!this.canCreate) {
      this.createError.set({
        kind: 'VALIDATION',
        title: 'Check your revision choices',
        message: this.strategy === 'LABEL'
          ? 'Select at least one Topic and keep the total at 50 questions or fewer.'
          : 'Choose between 1 and 50 questions.',
        retryable: false,
      });
      return;
    }

    const request = this.buildRequest();
    this.creating.set(true);
    this.createError.set(null);
    this.revisionService
      .createSession(request)
      .pipe(finalize(() => this.creating.set(false)))
      .subscribe({
        next: (session) => {
          this.toaster.success('Your questions are ready.', { title: 'Revision ready' });
          if (session.requested_strategy === 'SMART' && session.strategy_used === 'RANDOM') {
            this.toaster.warning('More learning evidence is needed, so Quick revision was used.', {
              title: 'Smart revision used Quick revision',
              duration: 6500,
            });
          }
          void this.router.navigate(['/app/revision-sessions', session.session_id]);
        },
        error: (error: HttpErrorResponse) => this.createError.set(mapRevisionError(error)),
      });
  }

  private buildRequest(): RevisionSessionCreateRequest {
    if (this.strategy === 'LABEL') {
      const request: LabelRevisionRequest = {
        quiz_type: 'LABEL',
        label_ids: [...this.selectedTopicIds()],
        questions_per_label: this.form.controls.questionsPerLabel.value,
        allow_ai_generation: false,
      };
      return request;
    }
    if (this.strategy === 'SMART') {
      const request: SmartRevisionRequest = {
        quiz_type: 'SMART',
        question_count: this.form.controls.questionCount.value,
        allow_ai_generation: false,
      };
      return request;
    }
    const request: RandomRevisionRequest = {
      quiz_type: 'RANDOM',
      question_count: this.form.controls.questionCount.value,
      allow_ai_generation: false,
    };
    return request;
  }
}
