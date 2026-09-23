import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
  signal,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  RenderTask,
  TextLayer,
} from 'pdfjs-dist';
import { finalize } from 'rxjs';
import { isApprovedCloudinaryMediaUrl } from '../../../core/security/media-url';
import {
  DictionaryDefinition,
  DictionaryService,
  normalizeDictionaryWord,
} from '../../../core/services/dictionary.service';
import { PdfJsLoaderService, PdfJsModule } from './pdfjs-loader.service';

type PdfViewerStatus = 'idle' | 'loading' | 'ready' | 'error';
type LookupStatus = 'idle' | 'loading' | 'found' | 'not-found' | 'error';

export interface PdfTextSelection {
  attachmentId: number;
  pageNumber: number;
  text: string;
}

export interface PdfPageRequest {
  pageNumber: number;
  token: number;
}

export type PdfNoteEditorForm = FormGroup<{
  sourceExcerpt: FormControl<string>;
  noteText: FormControl<string>;
}>;

interface SelectionMenuState {
  text: string;
  left: number;
  top: number;
}

@Component({
  selector: 'app-pdf-viewer',
  imports: [ReactiveFormsModule],
  templateUrl: './pdf-viewer.html',
  styleUrls: ['./pdf-viewer.css', './pdf-viewer-reading-tools.css'],
})
export class PdfViewer implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) url = '';
  @Input() title = 'Attached PDF';
  @Input() attachmentId = 0;
  @Input() pageRequest: PdfPageRequest | null = null;
  @Input() noteEditorOpen = false;
  @Input() noteEditorTitle = 'Personal PDF note';
  @Input() noteForm: PdfNoteEditorForm | null = null;
  @Input() noteSaving = false;
  @Input() noteSaveError: string | null = null;
  @Output() readonly noteRequested = new EventEmitter<PdfTextSelection>();
  @Output() readonly noteEditorClosed = new EventEmitter<void>();
  @Output() readonly noteSaveRequested = new EventEmitter<void>();

  @ViewChild('canvas', { static: true }) private canvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('textLayer', { static: true }) private textLayerElement!: ElementRef<HTMLDivElement>;
  @ViewChild('viewport', { static: true }) private viewport!: ElementRef<HTMLDivElement>;
  @ViewChild('viewer', { static: true }) private viewer!: ElementRef<HTMLElement>;

  readonly status = signal<PdfViewerStatus>('idle');
  readonly pageNumber = signal(1);
  readonly pageCount = signal(0);
  readonly zoom = signal(1);
  readonly rendering = signal(false);
  readonly errorMessage = signal('');
  readonly fullscreen = signal(false);
  readonly fullscreenSupported = signal(false);
  readonly fullscreenMessage = signal('');
  readonly textAvailable = signal(false);
  readonly selectionMenu = signal<SelectionMenuState | null>(null);
  readonly manualWord = signal('');
  readonly lookupStatus = signal<LookupStatus>('idle');
  readonly lookupResult = signal<DictionaryDefinition | null>(null);
  readonly lookupMessage = signal('');
  readonly lookupPanelOpen = signal(false);

  private viewReady = false;
  private loadGeneration = 0;
  private loadingTask: PDFDocumentLoadingTask | null = null;
  private documentProxy: PDFDocumentProxy | null = null;
  private renderTask: RenderTask | null = null;
  private textLayer: TextLayer | null = null;
  private pdfjs: PdfJsModule | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private resizeTimer: ReturnType<typeof setTimeout> | null = null;
  private loadTimer: ReturnType<typeof setTimeout> | null = null;
  private selectionTimer: ReturnType<typeof setTimeout> | null = null;
  private lastPageRequestToken = -1;

  constructor(
    private readonly loader: PdfJsLoaderService,
    private readonly dictionary: DictionaryService,
  ) {}

  ngAfterViewInit(): void {
    this.viewReady = true;
    const document = this.viewer.nativeElement.ownerDocument;
    this.fullscreenSupported.set(
      typeof this.viewer.nativeElement.requestFullscreen === 'function'
      && typeof document.exitFullscreen === 'function',
    );
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => this.scheduleRender());
      this.resizeObserver.observe(this.viewport.nativeElement);
    }
    void this.loadDocument();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['url'] && !changes['url'].firstChange && this.viewReady) {
      void this.loadDocument();
    } else if (changes['pageRequest'] && this.viewReady) {
      this.applyPageRequest();
    }
  }

  ngOnDestroy(): void {
    this.loadGeneration += 1;
    this.clearTimers();
    this.resizeObserver?.disconnect();
    this.destroyPdfResources();
    const document = this.viewer.nativeElement.ownerDocument;
    if (document.fullscreenElement === this.viewer.nativeElement) {
      void document.exitFullscreen().catch(() => undefined);
    }
  }

  @HostListener('document:fullscreenchange')
  handleFullscreenChange(): void {
    if (!this.viewReady) return;
    const active = this.viewer.nativeElement.ownerDocument.fullscreenElement
      === this.viewer.nativeElement;
    this.fullscreen.set(active);
    this.fullscreenMessage.set('');
    this.scheduleRender();
  }

  @HostListener('document:selectionchange')
  handleSelectionChange(): void {
    if (!this.viewReady || this.status() !== 'ready') return;
    if (this.selectionTimer) clearTimeout(this.selectionTimer);
    this.selectionTimer = setTimeout(() => this.captureTextSelection(), 40);
  }

  retry(): void {
    void this.loadDocument();
  }

  async toggleFullscreen(): Promise<void> {
    if (!this.fullscreenSupported()) {
      this.fullscreenMessage.set('Full screen is not supported by this browser.');
      return;
    }

    const element = this.viewer.nativeElement;
    const document = element.ownerDocument;
    this.fullscreenMessage.set('');
    try {
      if (document.fullscreenElement === element) await document.exitFullscreen();
      else await element.requestFullscreen();
    } catch {
      this.fullscreenMessage.set('Full screen could not be opened. Try again or open the PDF.');
    }
  }

  previousPage(): void {
    if (this.pageNumber() <= 1 || this.rendering()) return;
    this.clearReadingSelection();
    this.pageNumber.update((page) => page - 1);
    void this.renderCurrentPage(this.loadGeneration);
  }

  nextPage(): void {
    if (this.pageNumber() >= this.pageCount() || this.rendering()) return;
    this.clearReadingSelection();
    this.pageNumber.update((page) => page + 1);
    void this.renderCurrentPage(this.loadGeneration);
  }

  zoomIn(): void {
    if (this.rendering() || this.zoom() >= 2) return;
    this.clearReadingSelection();
    this.zoom.update((value) => Math.min(2, Number((value + 0.25).toFixed(2))));
    void this.renderCurrentPage(this.loadGeneration);
  }

  zoomOut(): void {
    if (this.rendering() || this.zoom() <= 0.75) return;
    this.clearReadingSelection();
    this.zoom.update((value) => Math.max(0.75, Number((value - 0.25).toFixed(2))));
    void this.renderCurrentPage(this.loadGeneration);
  }

  updateManualWord(event: Event): void {
    this.manualWord.set((event.target as HTMLInputElement).value);
  }

  openManualLookup(): void {
    if (this.noteEditorOpen) return;
    this.lookupPanelOpen.set(true);
    this.lookupStatus.set('idle');
    this.lookupMessage.set('');
  }

  defineSelectedWord(): void {
    const selection = this.selectionMenu();
    if (!selection) return;
    this.manualWord.set(selection.text);
    this.lookup(selection.text);
    this.selectionMenu.set(null);
  }

  submitManualLookup(event: Event): void {
    event.preventDefault();
    this.lookup(this.manualWord());
  }

  dismissLookup(): void {
    this.lookupPanelOpen.set(false);
    this.lookupStatus.set('idle');
    this.lookupResult.set(null);
    this.lookupMessage.set('');
  }

  addSelectedNote(): void {
    const selection = this.selectionMenu();
    if (!selection) return;
    this.dismissLookup();
    this.noteRequested.emit({
      attachmentId: this.attachmentId,
      pageNumber: this.pageNumber(),
      text: selection.text.slice(0, 500),
    });
    this.selectionMenu.set(null);
  }

  addManualNote(): void {
    if (this.noteEditorOpen) return;
    this.dismissLookup();
    this.noteRequested.emit({
      attachmentId: this.attachmentId,
      pageNumber: this.pageNumber(),
      text: '',
    });
  }

  dismissSelectionMenu(): void {
    this.selectionMenu.set(null);
  }

  closeNoteEditor(): void {
    if (!this.noteSaving) this.noteEditorClosed.emit();
  }

  saveNote(): void {
    if (!this.noteSaving) this.noteSaveRequested.emit();
  }

  canDefineSelection(): boolean {
    return normalizeDictionaryWord(this.selectionMenu()?.text ?? '') !== null;
  }

  zoomPercent(): number {
    return Math.round(this.zoom() * 100);
  }

  private async loadDocument(): Promise<void> {
    const generation = ++this.loadGeneration;
    this.clearTimers();
    this.destroyPdfResources();
    this.pageNumber.set(1);
    this.zoom.set(1);
    this.pageCount.set(0);
    this.errorMessage.set('');
    this.textAvailable.set(false);
    this.clearReadingSelection();

    if (!isApprovedCloudinaryMediaUrl(this.url)) {
      this.fail('This PDF address is not from an approved Revisee storage location.');
      return;
    }

    this.status.set('loading');
    try {
      const pdfjs = await this.loader.load();
      this.pdfjs = pdfjs;
      if (generation !== this.loadGeneration) return;

      const loadingTask = pdfjs.getDocument({
        url: this.url,
        withCredentials: false,
        cMapUrl: this.loader.assetUrl('cmaps/'),
        cMapPacked: true,
        iccUrl: this.loader.assetUrl('iccs/'),
        standardFontDataUrl: this.loader.assetUrl('standard_fonts/'),
        wasmUrl: this.loader.assetUrl('wasm/'),
      });
      this.loadingTask = loadingTask;
      const timeout = new Promise<never>((_resolve, reject) => {
        this.loadTimer = setTimeout(
          () => reject(new Error('PDF loading timed out.')),
          20_000,
        );
      });
      const documentProxy = await Promise.race([loadingTask.promise, timeout]);
      this.clearLoadTimer();
      if (generation !== this.loadGeneration) {
        await loadingTask.destroy();
        return;
      }

      this.documentProxy = documentProxy;
      this.pageCount.set(documentProxy.numPages);
      this.pageNumber.set(Math.min(
        Math.max(this.pageRequest?.pageNumber ?? 1, 1),
        documentProxy.numPages,
      ));
      if (this.pageRequest) this.lastPageRequestToken = this.pageRequest.token;
      const rendered = await this.renderCurrentPage(generation);
      if (rendered && generation === this.loadGeneration) this.status.set('ready');
    } catch {
      if (generation !== this.loadGeneration) return;
      this.clearLoadTimer();
      this.destroyPdfResources();
      this.fail('This PDF could not be loaded in Revisee. You can still open the original file.');
    }
  }

  private async renderCurrentPage(generation: number): Promise<boolean> {
    const documentProxy = this.documentProxy;
    if (!documentProxy || !this.viewReady) return false;

    this.rendering.set(true);
    this.textAvailable.set(false);
    this.clearReadingSelection();
    this.textLayer?.cancel();
    this.textLayer = null;
    try {
      const page = await documentProxy.getPage(this.pageNumber());
      if (generation !== this.loadGeneration) return false;

      const unscaled = page.getViewport({ scale: 1 });
      const availableWidth = Math.max(280, this.viewport.nativeElement.clientWidth - 32);
      const fitScale = Math.min(2.25, Math.max(0.5, availableWidth / unscaled.width));
      const scale = fitScale * this.zoom();
      const viewport = page.getViewport({ scale });
      const canvas = this.canvas.nativeElement;
      const context = canvas.getContext('2d', { alpha: false });
      if (!context) throw new Error('Canvas rendering is unavailable.');

      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      const textLayerElement = this.textLayerElement.nativeElement;
      textLayerElement.replaceChildren();
      textLayerElement.style.width = `${Math.floor(viewport.width)}px`;
      textLayerElement.style.height = `${Math.floor(viewport.height)}px`;
      textLayerElement.style.setProperty('--total-scale-factor', `${scale}`);

      const renderTask = page.render({
        canvas,
        canvasContext: context,
        viewport,
        transform: pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0],
      });
      this.renderTask = renderTask;
      const textContentPromise = page.getTextContent();
      const [, textContent] = await Promise.all([renderTask.promise, textContentPromise]);
      if (generation !== this.loadGeneration) return false;

      const hasText = textContent.items.some((item) => (
        'str' in item && typeof item.str === 'string' && item.str.trim().length > 0
      ));
      this.textAvailable.set(hasText);
      if (hasText && this.pdfjs) {
        const textLayer = new this.pdfjs.TextLayer({
          textContentSource: textContent,
          container: textLayerElement,
          viewport,
        });
        this.textLayer = textLayer;
        await textLayer.render();
      }
      return true;
    } catch {
      if (generation === this.loadGeneration) {
        this.fail('This PDF page could not be rendered. You can still open the original file.');
      }
      return false;
    } finally {
      if (generation === this.loadGeneration) this.rendering.set(false);
    }
  }

  private scheduleRender(): void {
    if (this.status() !== 'ready' || !this.documentProxy) return;
    if (this.resizeTimer) clearTimeout(this.resizeTimer);
    this.resizeTimer = setTimeout(() => {
      this.resizeTimer = null;
      if (this.rendering()) {
        this.scheduleRender();
        return;
      }
      void this.renderCurrentPage(this.loadGeneration);
    }, 100);
  }

  private fail(message: string): void {
    this.errorMessage.set(message);
    this.status.set('error');
    this.rendering.set(false);
  }

  private destroyPdfResources(): void {
    this.renderTask?.cancel();
    this.renderTask = null;
    this.textLayer?.cancel();
    this.textLayer = null;
    if (this.viewReady) this.textLayerElement.nativeElement.replaceChildren();
    if (this.loadingTask) void this.loadingTask.destroy();
    this.loadingTask = null;
    this.documentProxy = null;
    this.pdfjs = null;
  }

  private clearLoadTimer(): void {
    if (this.loadTimer) clearTimeout(this.loadTimer);
    this.loadTimer = null;
  }

  private clearTimers(): void {
    this.clearLoadTimer();
    if (this.resizeTimer) clearTimeout(this.resizeTimer);
    this.resizeTimer = null;
    if (this.selectionTimer) clearTimeout(this.selectionTimer);
    this.selectionTimer = null;
  }

  private captureTextSelection(): void {
    const element = this.textLayerElement.nativeElement;
    const selection = element.ownerDocument.getSelection();
    if (
      !selection
      || selection.rangeCount === 0
      || selection.isCollapsed
      || !selection.anchorNode
      || !selection.focusNode
      || !element.contains(selection.anchorNode)
      || !element.contains(selection.focusNode)
    ) {
      this.selectionMenu.set(null);
      return;
    }
    const text = selection.toString().replace(/\s+/gu, ' ').trim().slice(0, 500);
    if (!text) {
      this.selectionMenu.set(null);
      return;
    }
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    const left = Math.min(Math.max(rect.left + rect.width / 2, 90), window.innerWidth - 90);
    const top = Math.max(12, rect.top - 50);
    this.selectionMenu.set({ text, left, top });
  }

  private clearReadingSelection(): void {
    this.selectionMenu.set(null);
    if (this.viewReady) {
      const selection = this.viewer.nativeElement.ownerDocument.getSelection();
      if (selection && selection.anchorNode && this.viewer.nativeElement.contains(selection.anchorNode)) {
        selection.removeAllRanges();
      }
    }
  }

  private applyPageRequest(): void {
    const request = this.pageRequest;
    if (
      !request
      || request.token === this.lastPageRequestToken
      || !this.documentProxy
      || request.pageNumber < 1
    ) return;
    this.lastPageRequestToken = request.token;
    this.clearReadingSelection();
    this.pageNumber.set(Math.min(request.pageNumber, this.pageCount()));
    void this.renderCurrentPage(this.loadGeneration);
  }

  private lookup(value: string): void {
    const word = normalizeDictionaryWord(value);
    this.lookupPanelOpen.set(true);
    this.lookupResult.set(null);
    if (!word) {
      this.lookupStatus.set('error');
      this.lookupMessage.set('Enter one word using letters, apostrophes or hyphens.');
      return;
    }
    this.manualWord.set(word);
    this.lookupStatus.set('loading');
    this.lookupMessage.set('');
    this.dictionary.lookup(word).pipe(
      finalize(() => {
        if (this.lookupStatus() === 'loading') this.lookupStatus.set('error');
      }),
    ).subscribe({
      next: (definition) => {
        if (!definition) {
          this.lookupStatus.set('not-found');
          this.lookupMessage.set(`No dictionary definition was found for “${word}”.`);
          return;
        }
        this.lookupResult.set(definition);
        this.lookupStatus.set('found');
      },
      error: () => {
        this.lookupStatus.set('error');
        this.lookupMessage.set('The dictionary is unavailable. Check your connection and try again.');
      },
    });
  }
}
