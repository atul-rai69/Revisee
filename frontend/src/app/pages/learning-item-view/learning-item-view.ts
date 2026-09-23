import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize, Subject, takeUntil } from 'rxjs';
import { isApprovedCloudinaryMediaUrl } from '../../core/security/media-url';
import {
  LearningItem,
  LearningItemDetail,
  LearningItemQuestion,
  PdfNote,
} from '../../core/services/learning-item';
import {
  PdfPageRequest,
  PdfTextSelection,
  PdfViewer,
} from '../../shared/components/pdf-viewer/pdf-viewer';

interface PdfResource {
  id: number;
  name: string;
  url: string;
}

@Component({
  selector: 'app-learning-item-view',
  imports: [CommonModule, RouterLink, ReactiveFormsModule, PdfViewer],
  templateUrl: './learning-item-view.html',
  styleUrls: [
    './learning-item-view.css',
    './learning-item-view-media.css',
    './learning-item-pdf-notes.css',
  ],
})
export class LearningItemView implements OnInit, OnDestroy {
  itemId = 0;
  readonly item = signal<LearningItemDetail | null>(null);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  readonly labels = signal<string[]>([]);
  readonly imageUrls = signal<string[]>([]);
  readonly pdfResources = signal<PdfResource[]>([]);
  readonly rejectedPdfCount = signal(0);
  readonly selectedPdfIndex = signal(0);
  readonly selectedPdf = computed(() => this.pdfResources()[this.selectedPdfIndex()] ?? null);
  readonly questions = signal<LearningItemQuestion[]>([]);
  readonly previewQuestions = computed(() => this.questions().slice(0, 3));
  readonly pdfNotes = signal<PdfNote[]>([]);
  readonly notesLoading = signal(false);
  readonly notesError = signal<string | null>(null);
  readonly noteEditorOpen = signal(false);
  readonly editingNoteId = signal<number | null>(null);
  readonly noteAttachmentId = signal(0);
  readonly notePageNumber = signal(1);
  readonly noteSaving = signal(false);
  readonly noteSaveError = signal<string | null>(null);
  readonly deletingNoteId = signal<number | null>(null);
  readonly confirmDeleteNoteId = signal<number | null>(null);
  readonly pageRequest = signal<PdfPageRequest | null>(null);
  readonly noteForm = new FormGroup({
    sourceExcerpt: new FormControl('', {
      nonNullable: true,
      validators: [Validators.maxLength(500)],
    }),
    noteText: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(4000)],
    }),
  });

  lightboxOpen = false;
  currentImageIndex = 0;
  private readonly destroyed = new Subject<void>();
  private itemLoadGeneration = 0;
  private pageRequestToken = 0;

  constructor(
    private readonly learningItemService: LearningItem,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntil(this.destroyed)).subscribe((params) => {
      this.itemId = Number(params.get('id'));
      this.clearItem();
      if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
        this.loadError.set('This learning item address is invalid.');
        this.loading.set(false);
        return;
      }
      this.loadItem();
    });
  }

  ngOnDestroy(): void {
    this.itemLoadGeneration += 1;
    this.destroyed.next();
    this.destroyed.complete();
    if (this.lightboxOpen) document.body.style.overflow = '';
  }

  loadItem(): void {
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This learning item address is invalid.');
      this.loading.set(false);
      return;
    }

    const generation = ++this.itemLoadGeneration;
    this.clearItem();
    this.loading.set(true);
    this.loadError.set(null);
    this.learningItemService.getLearningItem(this.itemId, { localLoading: true })
      .pipe(finalize(() => {
        if (generation === this.itemLoadGeneration) this.loading.set(false);
      }))
      .subscribe({
        next: ({ data }) => {
          if (generation !== this.itemLoadGeneration) return;
          try {
            this.applyItem(data);
          } catch {
            this.clearItem();
            this.loadError.set('The learning item response could not be displayed. Try again.');
          }
        },
        error: (error: HttpErrorResponse) => {
          if (generation !== this.itemLoadGeneration) return;
          this.clearItem();
          this.loadError.set(error.status === 404
            ? 'This learning item is unavailable.'
            : 'The learning item could not be loaded. Try again.');
        },
      });
  }

  generateMoreQuestions(): void {
    const item = this.item();
    if (!item) return;
    void this.router.navigate(['/app/learning-items', item.id, 'questions']);
  }

  openLightbox(index: number): void {
    if (!this.imageUrls()[index]) return;
    this.currentImageIndex = index;
    this.lightboxOpen = true;
    document.body.style.overflow = 'hidden';
  }

  closeLightbox(): void {
    this.lightboxOpen = false;
    document.body.style.overflow = '';
  }

  selectImage(index: number): void {
    this.currentImageIndex = index;
  }

  selectPdf(index: number): void {
    if (!this.pdfResources()[index]) return;
    this.selectedPdfIndex.set(index);
    this.pageRequest.set(null);
    this.closeNoteEditor();
  }

  openNoteEditor(selection: PdfTextSelection): void {
    if (!this.pdfResources().some((resource) => resource.id === selection.attachmentId)) {
      this.noteSaveError.set('This PDF attachment is no longer available. Reload the item.');
      return;
    }
    this.editingNoteId.set(null);
    this.noteAttachmentId.set(selection.attachmentId);
    this.notePageNumber.set(selection.pageNumber);
    this.noteForm.reset({ sourceExcerpt: selection.text, noteText: '' });
    this.noteSaveError.set(null);
    this.noteEditorOpen.set(true);
  }

  editPdfNote(note: PdfNote): void {
    if (!this.pdfResources().some((resource) => resource.id === note.media_id)) return;
    this.editingNoteId.set(note.id);
    this.noteAttachmentId.set(note.media_id);
    this.notePageNumber.set(note.page_number);
    this.noteForm.reset({
      sourceExcerpt: note.source_excerpt ?? '',
      noteText: note.note_text,
    });
    this.noteSaveError.set(null);
    this.noteEditorOpen.set(true);
  }

  closeNoteEditor(): void {
    if (this.noteSaving()) return;
    this.noteEditorOpen.set(false);
    this.editingNoteId.set(null);
    this.noteAttachmentId.set(0);
    this.notePageNumber.set(1);
    this.noteSaveError.set(null);
    this.noteForm.reset({ sourceExcerpt: '', noteText: '' });
  }

  savePdfNote(): void {
    if (this.noteSaving()) return;
    this.noteForm.markAllAsTouched();
    const noteText = this.noteForm.controls.noteText.value.trim();
    const sourceExcerpt = this.noteForm.controls.sourceExcerpt.value.trim();
    if (this.noteForm.invalid || !noteText || this.noteAttachmentId() <= 0) {
      this.noteSaveError.set('Write a note of up to 4,000 characters before saving.');
      return;
    }
    const generation = this.itemLoadGeneration;
    const editingId = this.editingNoteId();
    const request = { note_text: noteText, source_excerpt: sourceExcerpt || null };
    const operation = editingId === null
      ? this.learningItemService.createPdfNote(this.itemId, {
        ...request,
        media_id: this.noteAttachmentId(),
        page_number: this.notePageNumber(),
      })
      : this.learningItemService.updatePdfNote(this.itemId, editingId, request);
    this.noteSaving.set(true);
    this.noteSaveError.set(null);
    operation.pipe(finalize(() => {
      if (generation === this.itemLoadGeneration) this.noteSaving.set(false);
    })).subscribe({
      next: () => {
        if (generation !== this.itemLoadGeneration) return;
        this.noteSaving.set(false);
        this.closeNoteEditor();
        this.loadPdfNotes(generation);
      },
      error: (error: HttpErrorResponse) => {
        if (generation !== this.itemLoadGeneration) return;
        this.noteSaveError.set(error.status === 404
          ? 'This learning item or PDF is no longer available.'
          : 'Your note could not be saved. Review it and try again.');
      },
    });
  }

  requestDeletePdfNote(noteId: number): void {
    this.confirmDeleteNoteId.set(noteId);
  }

  cancelDeletePdfNote(): void {
    if (!this.deletingNoteId()) this.confirmDeleteNoteId.set(null);
  }

  deletePdfNote(noteId: number): void {
    if (this.deletingNoteId() !== null) return;
    const generation = this.itemLoadGeneration;
    this.deletingNoteId.set(noteId);
    this.learningItemService.deletePdfNote(this.itemId, noteId).pipe(
      finalize(() => {
        if (generation === this.itemLoadGeneration) this.deletingNoteId.set(null);
      }),
    ).subscribe({
      next: () => {
        if (generation !== this.itemLoadGeneration) return;
        this.confirmDeleteNoteId.set(null);
        this.pdfNotes.update((notes) => notes.filter((note) => note.id !== noteId));
      },
      error: () => {
        if (generation !== this.itemLoadGeneration) return;
        this.notesError.set('The note could not be deleted. Try again.');
      },
    });
  }

  goToPdfNote(note: PdfNote): void {
    const index = this.pdfResources().findIndex((resource) => resource.id === note.media_id);
    if (index < 0) {
      this.notesError.set('The PDF attached to this note is no longer available.');
      return;
    }
    this.selectedPdfIndex.set(index);
    this.pageRequest.set({ pageNumber: note.page_number, token: ++this.pageRequestToken });
  }

  pdfName(mediaId: number): string {
    return this.pdfResources().find((resource) => resource.id === mediaId)?.name
      ?? 'Removed PDF attachment';
  }

  nextImage(): void {
    const imageCount = this.imageUrls().length;
    if (!imageCount) return;
    this.currentImageIndex = (this.currentImageIndex + 1) % imageCount;
  }

  previousImage(): void {
    const imageCount = this.imageUrls().length;
    if (!imageCount) return;
    this.currentImageIndex = (
      this.currentImageIndex - 1 + imageCount
    ) % imageCount;
  }

  @HostListener('document:keydown.escape')
  handleEscape(): void {
    if (this.lightboxOpen) {
      this.closeLightbox();
      return;
    }
    if (this.noteEditorOpen() && !this.noteSaving()) this.closeNoteEditor();
  }

  @HostListener('document:keydown.arrowright')
  handleRight(): void {
    if (this.lightboxOpen) this.nextImage();
  }

  @HostListener('document:keydown.arrowleft')
  handleLeft(): void {
    if (this.lightboxOpen) this.previousImage();
  }

  private applyItem(item: LearningItemDetail): void {
    const labels = this.splitValues(item.labels);
    const imageUrls = this.splitValues(item.image_urls)
      .filter((url) => this.isApprovedMediaUrl(url));
    const rawPdfUrls = this.splitValues(item.pdf_urls);
    const structuredPdfResources = item.pdf_resources ?? [];
    const approvedStructured = structuredPdfResources.filter((resource) => (
      isApprovedCloudinaryMediaUrl(resource.url)
    ));
    const approvedPdfUrls = rawPdfUrls.filter((url) => isApprovedCloudinaryMediaUrl(url));
    const pdfResources = (structuredPdfResources.length ? approvedStructured : approvedPdfUrls)
      .map((resource, index) => {
        const url = typeof resource === 'string' ? resource : resource.url;
        return {
        id: typeof resource === 'string' ? 0 : resource.id,
        name: typeof resource === 'string'
          ? this.resourceName(url, index)
          : resource.original_filename || this.resourceName(url, index),
        url,
      };});

    // Publish only after URL parsing and sanitization have completed safely.
    this.labels.set(labels);
    this.imageUrls.set(imageUrls);
    this.pdfResources.set(pdfResources);
    this.rejectedPdfCount.set(structuredPdfResources.length
      ? structuredPdfResources.length - approvedStructured.length
      : rawPdfUrls.length - approvedPdfUrls.length);
    this.selectedPdfIndex.set(0);
    this.questions.set(Array.isArray(item.questions) ? item.questions : []);
    this.item.set({
      ...item,
      key_points: Array.isArray(item.key_points) ? item.key_points : [],
      questions: Array.isArray(item.questions) ? item.questions : [],
    });
    this.loadPdfNotes(this.itemLoadGeneration);
  }

  private clearItem(): void {
    this.item.set(null);
    this.labels.set([]);
    this.imageUrls.set([]);
    this.pdfResources.set([]);
    this.rejectedPdfCount.set(0);
    this.selectedPdfIndex.set(0);
    this.questions.set([]);
    this.pdfNotes.set([]);
    this.notesLoading.set(false);
    this.notesError.set(null);
    this.noteSaving.set(false);
    this.noteEditorOpen.set(false);
    this.editingNoteId.set(null);
    this.noteAttachmentId.set(0);
    this.confirmDeleteNoteId.set(null);
    this.deletingNoteId.set(null);
    this.pageRequest.set(null);
    this.noteForm.reset({ sourceExcerpt: '', noteText: '' });
  }

  private splitValues(value: string | null): string[] {
    return value
      ? value.split(',').map((entry) => entry.trim()).filter(Boolean)
      : [];
  }

  private isApprovedMediaUrl(value: string): boolean {
    return isApprovedCloudinaryMediaUrl(value);
  }

  private resourceName(url: string, index: number): string {
    try {
      const filename = decodeURIComponent(new URL(url).pathname.split('/').pop() ?? '');
      return filename.toLocaleLowerCase().endsWith('.pdf')
        ? filename
        : `PDF attachment ${index + 1}`;
    } catch {
      return `Learning material ${index + 1}.pdf`;
    }
  }

  private loadPdfNotes(generation: number): void {
    this.notesLoading.set(true);
    this.notesError.set(null);
    this.learningItemService.listPdfNotes(this.itemId).pipe(
      finalize(() => {
        if (generation === this.itemLoadGeneration) this.notesLoading.set(false);
      }),
    ).subscribe({
      next: ({ notes }) => {
        if (generation !== this.itemLoadGeneration) return;
        this.pdfNotes.set(Array.isArray(notes) ? notes : []);
      },
      error: () => {
        if (generation !== this.itemLoadGeneration) return;
        this.notesError.set('Your PDF notes could not be loaded. Try again.');
      },
    });
  }

}
