import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { AICredential, AICredentialsService } from '../../core/services/ai-credentials.service';
import {
  LearningItem,
  LearningItemDetail,
  LearningItemQuestion,
  LearningItemOptionLabel,
  ManualQuestionRequest,
} from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-learning-item-questions',
  imports: [CommonModule, RouterLink, ReactiveFormsModule],
  templateUrl: './learning-item-questions.html',
  styleUrls: ['./learning-item-questions.css', './learning-item-question-generation.css'],
})
export class LearningItemQuestions implements OnInit {
  itemId = 0;
  readonly item = signal<LearningItemDetail | null>(null);
  readonly loading = signal(true);
  readonly generating = signal(false);
  readonly showGenerationForm = signal(false);
  readonly generationError = signal<string | null>(null);
  readonly credentials = signal<AICredential[]>([]);
  readonly credentialsLoading = signal(false);
  readonly credentialsError = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly revealedAnswers = new Set<number>();
  readonly showQuestionForm = signal(false);
  readonly savingQuestion = signal(false);
  readonly questionError = signal<string | null>(null);
  readonly questionForm;
  readonly generationForm;

  constructor(
    private readonly learningItemService: LearningItem,
    private readonly toaster: ToasterService,
    private readonly route: ActivatedRoute,
    private readonly credentialService: AICredentialsService,
    formBuilder: FormBuilder,
  ) {
    this.questionForm = formBuilder.nonNullable.group({
      question: ['', [Validators.required, Validators.maxLength(5000)]],
      optionA: ['', [Validators.required, Validators.maxLength(255)]],
      optionB: ['', [Validators.required, Validators.maxLength(255)]],
      optionC: ['', [Validators.required, Validators.maxLength(255)]],
      optionD: ['', [Validators.required, Validators.maxLength(255)]],
      correctOption: ['A' as LearningItemOptionLabel, Validators.required],
      explanation: ['', [Validators.required, Validators.maxLength(10000)]],
      difficulty: [2, [Validators.required, Validators.min(1), Validators.max(3)]],
      expectedTime: [30, [Validators.required, Validators.min(1), Validators.max(3600)]],
    });
    this.generationForm = formBuilder.group({
      generationSource: formBuilder.nonNullable.control<'REVISEE' | 'PERSONAL'>('REVISEE'),
      credentialId: formBuilder.control<number | null>(null),
      personalRemarks: formBuilder.nonNullable.control('', Validators.maxLength(2000)),
      questionCount: formBuilder.nonNullable.control(5, [Validators.min(1), Validators.max(10)]),
    });
  }

  ngOnInit(): void {
    this.itemId = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This question-bank address is invalid.');
      this.loading.set(false);
      return;
    }
    this.loadQuestions();
    this.loadCredentials();
  }

  loadCredentials(): void {
    if (this.credentialsLoading()) return;
    this.credentialsLoading.set(true);
    this.credentialsError.set(false);
    this.credentialService.list().pipe(finalize(() => this.credentialsLoading.set(false))).subscribe({
      next: (response) => {
        const valid = response.credentials.filter((credential) => credential.status === 'VALID');
        this.credentials.set(valid);
        this.generationForm.controls.credentialId.setValue(
          valid.find((credential) => credential.is_default)?.id ?? null,
        );
      },
      error: () => this.credentialsError.set(true),
    });
  }

  loadQuestions(): void {
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This question-bank address is invalid.');
      this.loading.set(false);
      return;
    }

    this.loading.set(true);
    this.loadError.set(null);
    this.learningItemService.getLearningItem(this.itemId, { localLoading: true })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: ({ data }) => {
          try {
            this.item.set({
              ...data,
              key_points: Array.isArray(data.key_points) ? data.key_points : [],
              questions: Array.isArray(data.questions) ? data.questions : [],
            });
            this.revealedAnswers.clear();
          } catch {
            this.item.set(null);
            this.loadError.set('The question-bank response could not be displayed. Try again.');
          }
        },
        error: (error: HttpErrorResponse) => {
          this.item.set(null);
          this.loadError.set(error.status === 404
            ? 'This learning item is unavailable.'
            : 'The question bank could not be loaded. Try again.');
        },
      });
  }

  generateMoreQuestions(): void {
    this.generationError.set(null);
    this.showGenerationForm.set(true);
  }

  closeGenerationForm(): void {
    if (!this.generating()) this.showGenerationForm.set(false);
  }

  submitGeneration(): void {
    const item = this.item();
    if (!item || this.generating()) return;
    const value = this.generationForm.getRawValue();
    if (
      this.generationForm.invalid
      || (value.generationSource === 'PERSONAL' && value.credentialId === null)
    ) {
      this.generationError.set('Choose a valid credential and question count.');
      return;
    }
    this.generating.set(true);
    this.generationError.set(null);
    this.learningItemService.generateQuestions(
      item.id,
      {
        generation_source: value.generationSource,
        credential_id: value.generationSource === 'PERSONAL' ? value.credentialId : null,
        personal_remarks: value.generationSource === 'PERSONAL'
          ? value.personalRemarks.trim() || null
          : null,
        question_count: value.questionCount,
      },
    ).pipe(finalize(() => this.generating.set(false)))
      .subscribe({
        next: (response) => {
          this.showGenerationForm.set(false);
          this.toaster.success(`${response.saved_count} new ${response.saved_count === 1 ? 'question was' : 'questions were'} appended.`, {
            title: 'Questions generated',
          });
          this.loadQuestions();
        },
        error: (error: HttpErrorResponse) => {
          this.generationError.set(this.generationErrorMessage(error));
        },
      });
  }

  toggleAnswer(question: LearningItemQuestion): void {
    if (this.revealedAnswers.has(question.number)) {
      this.revealedAnswers.delete(question.number);
    } else {
      this.revealedAnswers.add(question.number);
    }
  }

  isAnswerRevealed(question: LearningItemQuestion): boolean {
    return this.revealedAnswers.has(question.number);
  }

  difficultyLabel(difficulty: number): string {
    return ({ 1: 'Easy', 2: 'Medium', 3: 'Hard' })[difficulty] ?? `Level ${difficulty}`;
  }

  openQuestionForm(): void { this.questionError.set(null); this.showQuestionForm.set(true); }
  closeQuestionForm(): void { if (!this.savingQuestion()) this.showQuestionForm.set(false); }

  createQuestion(): void {
    if (this.savingQuestion()) return;
    this.questionForm.markAllAsTouched();
    const value = this.questionForm.getRawValue();
    const options = [value.optionA, value.optionB, value.optionC, value.optionD].map((entry) => entry.trim());
    if (this.questionForm.invalid || !value.question.trim() || !value.explanation.trim() || options.some((entry) => !entry)) {
      this.questionError.set('Complete every field with valid, non-blank content.');
      return;
    }
    if (new Set(options.map((entry) => entry.toLocaleLowerCase())).size !== 4) {
      this.questionError.set('Each answer option must be different.');
      return;
    }
    const request: ManualQuestionRequest = {
      question: value.question.trim(), option_a: options[0], option_b: options[1],
      option_c: options[2], option_d: options[3], correct_option: value.correctOption,
      explanation: value.explanation.trim(), difficulty: value.difficulty,
      expected_time_seconds: value.expectedTime,
    };
    this.savingQuestion.set(true); this.questionError.set(null);
    this.learningItemService.createQuestion(this.itemId, request)
      .pipe(finalize(() => this.savingQuestion.set(false)))
      .subscribe({
        next: () => {
          this.toaster.success('Question added to this learning item.', { title: 'Question saved' });
          this.questionForm.reset({ question: '', optionA: '', optionB: '', optionC: '', optionD: '', correctOption: 'A', explanation: '', difficulty: 2, expectedTime: 30 });
          this.showQuestionForm.set(false);
          this.loadQuestions();
        },
        error: (error: HttpErrorResponse) => {
          this.questionError.set(error.status === 409
            ? 'An equivalent question already exists in this question bank.'
            : error.status === 404 ? 'This learning item is unavailable.' : 'The question could not be saved. Try again.');
        },
      });
  }

  private generationErrorMessage(error: HttpErrorResponse): string {
    if (error.status === 404) return 'The learning item or selected credential is unavailable.';
    if (error.status === 422) return 'The selected Gemini key, remarks or source material was rejected.';
    if (error.status === 429) return 'Gemini quota or request limits were reached. Choose another option or try later.';
    if (error.status === 502) return 'Gemini returned malformed content. No questions were saved.';
    if (error.status === 503 || error.status === 0) return 'Gemini is temporarily unavailable. No questions were saved.';
    return 'The generated questions could not be saved. Try again.';
  }
}
