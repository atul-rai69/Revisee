import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import {
  LearningItem,
  LearningItemDetail,
  LearningItemQuestion,
} from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';

interface PdfResource {
  name: string;
  url: string;
  safeUrl: SafeResourceUrl;
}

@Component({
  selector: 'app-learning-item-view',
  imports: [CommonModule, RouterLink],
  templateUrl: './learning-item-view.html',
  styleUrls: ['./learning-item-view.css', './learning-item-view-media.css'],
})
export class LearningItemView implements OnInit, OnDestroy {
  itemId = 0;
  readonly item = signal<LearningItemDetail | null>(null);
  readonly loading = signal(true);
  readonly generating = signal(false);
  readonly loadError = signal<string | null>(null);

  readonly labels = signal<string[]>([]);
  readonly imageUrls = signal<string[]>([]);
  readonly pdfResources = signal<PdfResource[]>([]);
  readonly questions = signal<LearningItemQuestion[]>([]);
  readonly previewQuestions = computed(() => this.questions().slice(0, 3));

  lightboxOpen = false;
  currentImageIndex = 0;

  constructor(
    private readonly learningItemService: LearningItem,
    private readonly toaster: ToasterService,
    private readonly route: ActivatedRoute,
    private readonly sanitizer: DomSanitizer,
  ) {}

  ngOnInit(): void {
    this.itemId = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This learning item address is invalid.');
      this.loading.set(false);
      return;
    }
    this.loadItem();
  }

  ngOnDestroy(): void {
    if (this.lightboxOpen) document.body.style.overflow = '';
  }

  loadItem(): void {
    if (!Number.isInteger(this.itemId) || this.itemId <= 0) {
      this.loadError.set('This learning item address is invalid.');
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
            this.applyItem(data);
          } catch {
            this.clearItem();
            this.loadError.set('The learning item response could not be displayed. Try again.');
          }
        },
        error: (error: HttpErrorResponse) => {
          this.clearItem();
          this.loadError.set(error.status === 404
            ? 'This learning item is unavailable.'
            : 'The learning item could not be loaded. Try again.');
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
          this.toaster.success('New revision questions are ready.', {
            title: 'Questions generated',
          });
          this.loadItem();
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
    if (this.lightboxOpen) this.closeLightbox();
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
    const pdfResources = this.splitValues(item.pdf_urls)
      .filter((url) => this.isApprovedMediaUrl(url))
      .map((url, index) => ({
        name: this.resourceName(url, index),
        url,
        safeUrl: this.sanitizer.bypassSecurityTrustResourceUrl(url),
      }));

    // Publish only after URL parsing and sanitization have completed safely.
    this.labels.set(labels);
    this.imageUrls.set(imageUrls);
    this.pdfResources.set(pdfResources);
    this.questions.set(Array.isArray(item.questions) ? item.questions : []);
    this.item.set({
      ...item,
      key_points: Array.isArray(item.key_points) ? item.key_points : [],
      questions: Array.isArray(item.questions) ? item.questions : [],
    });
  }

  private clearItem(): void {
    this.item.set(null);
    this.labels.set([]);
    this.imageUrls.set([]);
    this.pdfResources.set([]);
    this.questions.set([]);
  }

  private splitValues(value: string | null): string[] {
    return value
      ? value.split(',').map((entry) => entry.trim()).filter(Boolean)
      : [];
  }

  private isApprovedMediaUrl(value: string): boolean {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'https:' && parsed.hostname === 'res.cloudinary.com';
    } catch {
      return false;
    }
  }

  private resourceName(url: string, index: number): string {
    try {
      const filename = decodeURIComponent(new URL(url).pathname.split('/').pop() ?? '');
      return filename || `Learning material ${index + 1}.pdf`;
    } catch {
      return `Learning material ${index + 1}.pdf`;
    }
  }

  private isGloballyReported(error: HttpErrorResponse): boolean {
    return error.status === 0 || error.status === 401 || error.status === 403 || error.status >= 500;
  }
}
