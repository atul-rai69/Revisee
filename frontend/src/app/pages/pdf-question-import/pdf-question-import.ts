import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, OnDestroy, OnInit, ViewChild, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom, Subject, takeUntil } from 'rxjs';
import { AICredential, AICredentialsService } from '../../core/services/ai-credentials.service';
import { DashboardService, LearningItemsSummary } from '../../core/services/dashboard-service';
import { LearningItem, LearningItemDetail } from '../../core/services/learning-item';
import {
  PdfDraftGenerationResponse,
  PdfQuestionDraftContract,
  PdfQuestionImportResponse,
  PdfQuestionImportService,
  PdfSourcePageRequest,
} from '../../core/services/pdf-question-import.service';
import {
  PdfTextExtractionError,
  PdfTextExtractionResult,
  PdfTextExtractorService,
  MAX_PDF_QUESTION_FILE_BYTES,
  validatePdfQuestionFile,
} from '../../shared/components/pdf-viewer/pdf-text-extractor.service';
import {
  PdfQuestionDraft,
  PdfQuestionOption,
  parseExistingPdfQuestions,
} from './pdf-question-parser';

type WorkflowMode = 'EXTRACT' | 'GENERATE';
type WorkflowState = 'SETUP' | 'EXTRACTING' | 'GENERATING' | 'REVIEW' | 'OCR_REQUIRED' | 'NO_RESULTS';

@Component({
  selector: 'app-pdf-question-import',
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './pdf-question-import.html',
  styleUrls: [
    './pdf-question-import.css',
    './pdf-question-import-upload.css',
    './pdf-question-import-responsive.css',
  ],
})
export class PdfQuestionImport implements OnInit, OnDestroy {
  @ViewChild('reviewHeading') private reviewHeading?: ElementRef<HTMLElement>;

  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly item = signal<LearningItemDetail | null>(null);
  readonly selectedFile = signal<File | null>(null);
  readonly filePageCount = signal<number | null>(null);
  readonly fileError = signal<string | null>(null);
  readonly inspectingFile = signal(false);
  readonly dragActive = signal(false);
  readonly destinations = signal<LearningItemsSummary[]>([]);
  readonly credentials = signal<AICredential[]>([]);
  readonly workflowState = signal<WorkflowState>('SETUP');
  readonly progressCompleted = signal(0);
  readonly progressTotal = signal(0);
  readonly drafts = signal<PdfQuestionDraft[]>([]);
  readonly extracted = signal<PdfTextExtractionResult | null>(null);
  readonly workflowError = signal<string | null>(null);
  readonly workflowNotice = signal<string | null>(null);
  readonly importing = signal(false);
  readonly importError = signal<string | null>(null);
  readonly importResult = signal<PdfQuestionImportResponse | null>(null);
  readonly destinationQuestionCount = signal<number | null>(null);
  readonly optionLabels: readonly PdfQuestionOption[] = ['A', 'B', 'C', 'D'];
  readonly maxFileMegabytes = MAX_PDF_QUESTION_FILE_BYTES / 1024 / 1024;

  readonly setupForm;
  readonly importForm;
  itemId = 0;

  private workController: AbortController | null = null;
  private readonly destroyed = new Subject<void>();

  constructor(
    formBuilder: FormBuilder,
    private readonly route: ActivatedRoute,
    private readonly learningItems: LearningItem,
    private readonly dashboards: DashboardService,
    private readonly credentialsService: AICredentialsService,
    private readonly extractor: PdfTextExtractorService,
    private readonly pdfQuestions: PdfQuestionImportService,
  ) {
    this.setupForm = formBuilder.nonNullable.group({
      mode: ['EXTRACT' as WorkflowMode, Validators.required],
      pageSelection: ['ENTIRE' as 'ENTIRE' | 'CUSTOM', Validators.required],
      firstPage: [1, [Validators.required, Validators.min(1)]],
      lastPage: [1, [Validators.required, Validators.min(1)]],
      questionCount: [5, [Validators.required, Validators.min(1), Validators.max(10)]],
      difficulty: [2, [Validators.required, Validators.min(1), Validators.max(3)]],
      focusInstructions: ['', Validators.maxLength(2000)],
      generationSource: ['REVISEE' as 'REVISEE' | 'PERSONAL', Validators.required],
      credentialId: formBuilder.control<number | null>(null),
    });
    this.importForm = formBuilder.nonNullable.group({
      destinationId: [0, [Validators.required, Validators.min(1)]],
    });
  }

  ngOnInit(): void {
    this.itemId = Number(this.route.snapshot.paramMap.get('learningItemId'));
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This PDF question-import address is invalid.');
      this.loading.set(false);
      return;
    }
    const requestedMode = this.route.snapshot.queryParamMap.get('mode');
    if (requestedMode === 'GENERATE' || requestedMode === 'EXTRACT') {
      this.setupForm.controls.mode.setValue(requestedMode);
    }
    this.loadItem();
    this.loadDestinations();
    this.loadCredentials();
  }

  ngOnDestroy(): void {
    this.workController?.abort();
    this.clearSensitiveDraftState();
    this.selectedFile.set(null);
    this.destroyed.next();
    this.destroyed.complete();
  }

  async startWorkflow(): Promise<void> {
    if (this.isBusy()) return;
    this.setupForm.markAllAsTouched();
    const value = this.setupForm.getRawValue();
    if (
      this.setupForm.invalid
      || (value.pageSelection === 'CUSTOM' && (
        value.lastPage < value.firstPage
        || value.lastPage > (this.filePageCount() ?? 0)
      ))
      || (value.mode === 'GENERATE'
        && value.generationSource === 'PERSONAL'
        && value.credentialId === null)
    ) {
      this.workflowError.set('Review the page range and generation options before continuing.');
      return;
    }
    const file = this.selectedFile();
    if (!file) {
      this.workflowError.set('Choose a valid PDF from your device before continuing.');
      return;
    }

    this.clearSensitiveDraftState();
    this.workflowError.set(null);
    this.workflowNotice.set(null);
    this.importResult.set(null);
    this.progressCompleted.set(0);
    this.progressTotal.set(0);
    this.workflowState.set('EXTRACTING');
    const controller = new AbortController();
    this.workController = controller;
    try {
      const result = await this.extractor.extract(file, {
        firstPage: value.pageSelection === 'CUSTOM' ? value.firstPage : undefined,
        lastPage: value.pageSelection === 'CUSTOM' ? value.lastPage : undefined,
        signal: controller.signal,
        onProgress: (completed, total) => {
          this.progressCompleted.set(completed);
          this.progressTotal.set(total);
        },
      });
      this.extracted.set(result);
      const usablePages = result.pages.filter((page) => page.has_usable_text);
      if (!usablePages.length) {
        this.workflowState.set('OCR_REQUIRED');
        return;
      }
      if (result.scannedPageNumbers.length) {
        this.workflowNotice.set(
          `${result.scannedPageNumbers.length} selected page(s) had no usable text and were skipped.`,
        );
      }
      if (value.mode === 'EXTRACT') {
        const parsed = parseExistingPdfQuestions(usablePages);
        this.drafts.set(parsed);
        this.workflowState.set(parsed.length ? 'REVIEW' : 'NO_RESULTS');
        if (parsed.length) this.focusReview();
        return;
      }
      await this.requestAiDrafts('GENERATE');
    } catch (error: unknown) {
      if (this.isAbort(error)) return;
      this.workflowError.set(this.extractionErrorMessage(error));
      this.workflowState.set('SETUP');
    } finally {
      if (this.workController === controller) this.workController = null;
    }
  }

  cancelExtraction(): void {
    this.workController?.abort();
    this.workflowState.set('SETUP');
    this.progressCompleted.set(0);
    this.progressTotal.set(0);
  }

  onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.item(0);
    input.value = '';
    if (file) void this.selectPdfFile(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!this.isBusy()) this.dragActive.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.dragActive.set(false);
  }

  onFileDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragActive.set(false);
    const file = event.dataTransfer?.files.item(0);
    if (file) void this.selectPdfFile(file);
  }

  async selectPdfFile(file: File): Promise<void> {
    this.workController?.abort();
    this.clearSensitiveDraftState();
    this.importResult.set(null);
    this.workflowNotice.set(null);
    this.workflowError.set(null);
    this.fileError.set(null);
    this.filePageCount.set(null);
    this.workflowState.set('SETUP');
    try {
      validatePdfQuestionFile(file);
    } catch (error: unknown) {
      this.selectedFile.set(null);
      this.fileError.set(this.extractionErrorMessage(error));
      return;
    }

    this.selectedFile.set(file);
    this.inspectingFile.set(true);
    const controller = new AbortController();
    this.workController = controller;
    try {
      const pageCount = await this.extractor.inspect(file, controller.signal);
      if (controller.signal.aborted) return;
      this.filePageCount.set(pageCount);
      this.setupForm.patchValue({ firstPage: 1, lastPage: pageCount });
    } catch (error: unknown) {
      if (this.isAbort(error)) return;
      this.selectedFile.set(null);
      this.fileError.set(this.extractionErrorMessage(error));
    } finally {
      if (this.workController === controller) {
        this.workController = null;
        this.inspectingFile.set(false);
      }
    }
  }

  removeSelectedFile(): void {
    this.workController?.abort();
    this.workController = null;
    this.inspectingFile.set(false);
    this.selectedFile.set(null);
    this.filePageCount.set(null);
    this.fileError.set(null);
    this.workflowState.set('SETUP');
    this.clearSensitiveDraftState();
    this.importResult.set(null);
  }

  async tryAiAssistedParsing(): Promise<void> {
    if (this.isBusy() || !this.extracted()) return;
    const value = this.setupForm.getRawValue();
    if (value.generationSource === 'PERSONAL' && value.credentialId === null) {
      this.workflowError.set('Choose a valid Gemini credential first.');
      return;
    }
    await this.requestAiDrafts('PARSE');
  }

  updateDraft(
    clientId: string,
    field: 'question' | 'explanation' | 'difficulty' | 'expected_time_seconds' | 'correct_option',
    event: Event,
  ): void {
    const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
    this.drafts.update((drafts) => drafts.map((draft) => {
      if (draft.clientId !== clientId) return draft;
      if (field === 'difficulty' || field === 'expected_time_seconds') {
        return { ...draft, [field]: Number(target.value) };
      }
      if (field === 'correct_option') {
        return { ...draft, correct_option: target.value as PdfQuestionOption || null };
      }
      return { ...draft, [field]: target.value };
    }));
  }

  updateOption(clientId: string, label: PdfQuestionOption, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.drafts.update((drafts) => drafts.map((draft) => draft.clientId === clientId
      ? { ...draft, options: { ...draft.options, [label]: value } }
      : draft));
  }

  toggleDraft(clientId: string, selected: boolean): void {
    this.drafts.update((drafts) => drafts.map((draft) => draft.clientId === clientId
      ? { ...draft, selected }
      : draft));
  }

  removeDraft(clientId: string): void {
    this.drafts.update((drafts) => drafts.filter((draft) => draft.clientId !== clientId));
  }

  draftIssues(draft: PdfQuestionDraft): string[] {
    const issues = draft.validation_issues.filter((issue) => issue.startsWith('Low model'));
    if (!draft.question.trim()) issues.push('Question text is required.');
    const normalizedOptions = (['A', 'B', 'C', 'D'] as const)
      .map((label) => draft.options[label].trim().toLocaleLowerCase());
    for (const [index, value] of normalizedOptions.entries()) {
      if (!value) issues.push(`Option ${(['A', 'B', 'C', 'D'] as const)[index]} is missing.`);
    }
    if (normalizedOptions.every(Boolean) && new Set(normalizedOptions).size !== 4) {
      issues.push('All four options must be different.');
    }
    if (!draft.correct_option) issues.push('Choose the correct answer before importing.');
    if (!draft.explanation?.trim()) issues.push('Add an explanation before importing.');
    if (!Number.isInteger(draft.difficulty) || draft.difficulty < 1 || draft.difficulty > 3) {
      issues.push('Difficulty must be between 1 and 3.');
    }
    if (!Number.isInteger(draft.expected_time_seconds) || draft.expected_time_seconds < 1) {
      issues.push('Expected time must be positive.');
    }
    return issues;
  }

  draftBlockingIssues(draft: PdfQuestionDraft): string[] {
    return this.draftIssues(draft).filter((issue) => !issue.startsWith('Low model'));
  }

  selectedCount(): number {
    return this.drafts().filter((draft) => draft.selected).length;
  }

  async importSelected(): Promise<void> {
    if (this.importing()) return;
    const source = this.extracted();
    const selected = this.drafts().filter((draft) => draft.selected);
    const destinationId = this.importForm.controls.destinationId.value;
    if (!source || destinationId <= 0 || !selected.length) {
      this.importError.set('Choose a destination and at least one draft.');
      return;
    }
    if (selected.some((draft) => this.draftBlockingIssues(draft).length > 0)) {
      this.importError.set('Resolve every warning on selected drafts before importing.');
      return;
    }
    this.importing.set(true);
    this.importError.set(null);
    this.importResult.set(null);
    try {
      const response = await firstValueFrom(this.pdfQuestions.importQuestions(
        this.itemId,
        {
          source_filename: this.selectedFile()?.name ?? '',
          destination_learning_item_id: destinationId,
          source_pages: this.sourcePages(source),
          questions: selected.map((draft) => this.toContract(draft)),
        },
      ).pipe(takeUntil(this.destroyed)));
      this.importResult.set(response);
      if (response.rejected_count === 0) {
        this.drafts.update((drafts) => drafts.filter((draft) => !selected.some(
          (entry) => entry.clientId === draft.clientId,
        )));
      }
      const canonical = await firstValueFrom(this.learningItems.getLearningItem(
        destinationId,
        { localLoading: true },
      ).pipe(takeUntil(this.destroyed)));
      this.destinationQuestionCount.set(canonical.data.questions.length);
    } catch (error: unknown) {
      this.importError.set(this.importErrorMessage(error));
    } finally {
      this.importing.set(false);
    }
  }

  isBusy(): boolean {
    return this.inspectingFile()
      || this.workflowState() === 'EXTRACTING'
      || this.workflowState() === 'GENERATING';
  }

  private loadItem(): void {
    this.learningItems.getLearningItem(this.itemId, { localLoading: true })
      .pipe(takeUntil(this.destroyed))
      .subscribe({
        next: ({ data }) => {
          this.item.set(data);
          this.importForm.controls.destinationId.setValue(data.id);
          this.loading.set(false);
        },
        error: () => {
          this.loadError.set('The learning item could not be loaded.');
          this.loading.set(false);
        },
      });
  }

  private loadDestinations(): void {
    this.dashboards.getLearningItemSummary({ localLoading: true })
      .pipe(takeUntil(this.destroyed))
      .subscribe({
        next: (response) => this.destinations.set(response.data),
        error: () => this.loadError.set('Owned learning items could not be loaded.'),
      });
  }

  private loadCredentials(): void {
    this.credentialsService.list().pipe(takeUntil(this.destroyed)).subscribe({
      next: (response) => {
        const valid = response.credentials.filter((credential) => credential.status === 'VALID');
        this.credentials.set(valid);
        this.setupForm.controls.credentialId.setValue(
          valid.find((credential) => credential.is_default)?.id ?? null,
        );
      },
      error: () => this.credentials.set([]),
    });
  }

  private async requestAiDrafts(mode: 'PARSE' | 'GENERATE'): Promise<void> {
    const source = this.extracted();
    if (!source) return;
    const value = this.setupForm.getRawValue();
    this.workflowState.set('GENERATING');
    this.workflowError.set(null);
    try {
      const response = await firstValueFrom(this.pdfQuestions.generateDrafts(
        this.itemId,
        {
          source_filename: this.selectedFile()?.name ?? '',
          mode,
          source_pages: this.sourcePages(source),
          question_count: value.questionCount,
          difficulty: value.difficulty,
          focus_instructions: value.focusInstructions.trim() || null,
          generation_source: value.generationSource,
          credential_id: value.generationSource === 'PERSONAL' ? value.credentialId : null,
        },
      ).pipe(takeUntil(this.destroyed)));
      const drafts = this.fromResponse(response);
      this.drafts.set(drafts);
      this.workflowState.set(drafts.length ? 'REVIEW' : 'NO_RESULTS');
      const coverage = response.coverage_page_numbers.join(', ');
      const resultNotice = response.partial || response.rejected_count
        ? `Returned ${response.returned_count} of ${response.requested_count} requested drafts; unsupported output was omitted. `
        : '';
      this.workflowNotice.set(
        `${resultNotice}Grounding used page${response.coverage_page_numbers.length === 1 ? '' : 's'} ${coverage} from the selected range.`,
      );
      if (drafts.length) this.focusReview();
    } catch (error: unknown) {
      this.workflowError.set(this.providerErrorMessage(error));
      this.workflowState.set('SETUP');
    }
  }

  private fromResponse(response: PdfDraftGenerationResponse): PdfQuestionDraft[] {
    return response.drafts.map((draft) => ({
      ...draft,
      clientId: crypto.randomUUID(),
      selected: true,
    }));
  }

  private sourcePages(source: PdfTextExtractionResult): PdfSourcePageRequest[] {
    return source.pages.map(({ page_number, text }) => ({ page_number, text }));
  }

  private toContract(draft: PdfQuestionDraft): PdfQuestionDraftContract {
    return {
      question: draft.question.trim(),
      options: {
        A: draft.options.A.trim(),
        B: draft.options.B.trim(),
        C: draft.options.C.trim(),
        D: draft.options.D.trim(),
      },
      correct_option: draft.correct_option,
      explanation: draft.explanation?.trim() || null,
      difficulty: draft.difficulty,
      expected_time_seconds: draft.expected_time_seconds,
      source_page: draft.source_page,
      source_excerpt: draft.source_excerpt,
      confidence: draft.confidence,
      validation_issues: this.draftIssues(draft),
    };
  }

  private focusReview(): void {
    setTimeout(() => this.reviewHeading?.nativeElement.focus(), 0);
  }

  private clearSensitiveDraftState(): void {
    this.extracted.set(null);
    this.drafts.set([]);
    this.importError.set(null);
    this.destinationQuestionCount.set(null);
  }

  private extractionErrorMessage(error: unknown): string {
    return error instanceof PdfTextExtractionError
      ? error.message
      : 'The PDF could not be read. Try again or open the original file.';
  }

  private providerErrorMessage(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) return 'Question drafts could not be prepared.';
    if (error.status === 404) return 'The learning item or selected Gemini credential is unavailable.';
    if (error.status === 422) return 'The selected pages, credential, or instructions were rejected.';
    if (error.status === 429) return 'Gemini quota or concurrency limits were reached. No drafts were saved.';
    if (error.status === 502) return 'Gemini returned malformed or ungrounded output. No drafts were saved.';
    if (error.status === 503 || error.status === 0) return 'Gemini is unavailable. No drafts were saved.';
    return 'Question drafts could not be prepared. Try again.';
  }

  private importErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 404) {
      return 'The source or destination learning item is no longer available.';
    }
    if (error instanceof HttpErrorResponse && error.status === 422) {
      return 'One or more selected drafts failed server validation. Review the source evidence.';
    }
    return 'The questions were not imported. Nothing was partially saved; try again.';
  }

  private isAbort(error: unknown): boolean {
    return error instanceof DOMException && error.name === 'AbortError';
  }
}
