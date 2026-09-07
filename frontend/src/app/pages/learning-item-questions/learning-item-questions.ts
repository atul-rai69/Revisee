import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import {
  LearningItem,
  LearningItemDetail,
  LearningItemQuestion,
} from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';

@Component({
  selector: 'app-learning-item-questions',
  imports: [CommonModule, RouterLink],
  templateUrl: './learning-item-questions.html',
  styleUrl: './learning-item-questions.css',
})
export class LearningItemQuestions implements OnInit {
  itemId = 0;
  readonly item = signal<LearningItemDetail | null>(null);
  readonly loading = signal(true);
  readonly generating = signal(false);
  readonly loadError = signal<string | null>(null);
  readonly revealedAnswers = new Set<number>();

  constructor(
    private readonly learningItemService: LearningItem,
    private readonly toaster: ToasterService,
    private readonly route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    this.itemId = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This question-bank address is invalid.');
      this.loading.set(false);
      return;
    }
    this.loadQuestions();
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
    const item = this.item();
    if (!item || this.generating()) return;
    this.generating.set(true);
    this.learningItemService.generateRevisionContent(
      item.id,
      item.title,
      item.description_text ?? '',
    ).pipe(finalize(() => this.generating.set(false)))
      .subscribe({
        next: () => {
          this.toaster.success('The question bank has been refreshed.', {
            title: 'Questions generated',
          });
          this.loadQuestions();
        },
        error: (error: HttpErrorResponse) => {
          if (this.isGloballyReported(error)) return;
          const message = error.status === 404
            ? 'This learning item is unavailable.'
            : 'Questions could not be generated. Try again.';
          this.toaster.error(message, { title: 'Generation failed' });
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

  private isGloballyReported(error: HttpErrorResponse): boolean {
    return error.status === 0 || error.status === 401 || error.status === 403 || error.status >= 500;
  }
}
