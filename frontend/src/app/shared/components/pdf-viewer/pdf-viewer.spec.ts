import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormControl, FormGroup } from '@angular/forms';
import { vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { DictionaryService } from '../../../core/services/dictionary.service';
import { PdfViewer } from './pdf-viewer';
import { PdfJsLoaderService } from './pdfjs-loader.service';

const approvedUrl = 'https://res.cloudinary.com/revisee/raw/upload/notes.pdf';

class FakePdfJsLoader {
  calls = 0;
  shouldFail = false;
  readonly destroy = vi.fn(() => Promise.resolve());
  readonly renderCancel = vi.fn();
  readonly getPage = vi.fn((pageNumber: number) => Promise.resolve({
    getViewport: ({ scale }: { scale: number }) => ({
      width: 600 * scale,
      height: 800 * scale,
    }),
    render: () => ({ promise: Promise.resolve(), cancel: this.renderCancel }),
    getTextContent: () => Promise.resolve({
      items: this.hasText ? [{ str: 'Learning', dir: 'ltr', width: 50, height: 10, transform: [1, 0, 0, 1, 10, 20], fontName: 'sans' }] : [],
      styles: {},
      lang: null,
    }),
    pageNumber,
  }));
  hasText = true;

  load() {
    this.calls += 1;
    if (this.shouldFail) return Promise.reject(new Error('unavailable'));
    return Promise.resolve({
      GlobalWorkerOptions: { workerSrc: '' },
      TextLayer: class {
        constructor(private readonly options: { container: HTMLElement }) {}
        render() {
          const span = document.createElement('span');
          span.textContent = 'Learning';
          this.options.container.append(span);
          return Promise.resolve();
        }
        cancel() {}
      },
      getDocument: () => ({
        promise: Promise.resolve({ numPages: 2, getPage: this.getPage }),
        destroy: this.destroy,
      }),
    });
  }

  assetUrl(path: string): string {
    return `/assets/pdfjs/${path}`;
  }
}

describe('PdfViewer', () => {
  let fixture: ComponentFixture<PdfViewer>;
  let component: PdfViewer;
  let loader: FakePdfJsLoader;
  let originalGetContext: typeof HTMLCanvasElement.prototype.getContext;
  const dictionary = {
    lookup: vi.fn(() => of({
      word: 'Learning',
      partOfSpeech: 'noun',
      definition: 'The acquisition of knowledge.',
      sourceLabel: 'Datamuse · WordNet and Wiktionary',
      sourceUrl: 'https://www.datamuse.com/api/',
    })),
  };

  beforeEach(async () => {
    originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = (() => (
      {} as CanvasRenderingContext2D
    )) as unknown as typeof HTMLCanvasElement.prototype.getContext;

    await TestBed.configureTestingModule({
      imports: [PdfViewer],
      providers: [
        { provide: PdfJsLoaderService, useClass: FakePdfJsLoader },
        { provide: DictionaryService, useValue: dictionary },
      ],
    }).compileComponents();
    loader = TestBed.inject(PdfJsLoaderService) as unknown as FakePdfJsLoader;
  });

  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = originalGetContext;
  });

  async function create(url = approvedUrl): Promise<void> {
    fixture = TestBed.createComponent(PdfViewer);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('url', url);
    fixture.componentRef.setInput('title', 'Study notes');
    fixture.componentRef.setInput('attachmentId', 9);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('renders a verified PDF and supports page navigation', async () => {
    await create();
    await vi.waitFor(() => expect(component.status()).toBe('ready'));
    fixture.detectChanges();

    expect(component.pageCount()).toBe(2);
    expect(loader.getPage).toHaveBeenCalledWith(1);
    const fallback = (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLAnchorElement>('.pdf-toolbar a');
    expect(fallback?.href).toBe(approvedUrl);

    component.nextPage();
    await vi.waitFor(() => expect(loader.getPage).toHaveBeenCalledWith(2));
    fixture.detectChanges();
    expect(component.pageNumber()).toBe(2);
    expect(loader.getPage).toHaveBeenCalledWith(2);

    await vi.waitFor(() => expect(component.rendering()).toBe(false));
    component.zoomIn();
    await vi.waitFor(() => expect(component.zoom()).toBe(1.25));
    await vi.waitFor(() => expect(component.textAvailable()).toBe(true));
  });

  it('offers define and note actions for selected PDF text', async () => {
    await create();
    await vi.waitFor(() => expect(component.status()).toBe('ready'));
    const span = (fixture.nativeElement as HTMLElement).querySelector('.textLayer span');
    expect(span).not.toBeNull();
    const range = document.createRange();
    range.selectNodeContents(span as Node);
    Object.defineProperty(range, 'getBoundingClientRect', {
      value: () => ({ left: 100, top: 100, width: 50, height: 16, right: 150, bottom: 116 }),
    });
    const selection = document.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    document.dispatchEvent(new Event('selectionchange'));
    await new Promise((resolve) => setTimeout(resolve, 60));
    fixture.detectChanges();

    expect(component.selectionMenu()?.text).toBe('Learning');
    const noteSpy = vi.fn();
    component.noteRequested.subscribe(noteSpy);
    component.addSelectedNote();
    expect(noteSpy).toHaveBeenCalledWith({ attachmentId: 9, pageNumber: 1, text: 'Learning' });

    component.openManualLookup();
    component.updateManualWord({ target: { value: 'Learning' } } as unknown as Event);
    component.submitManualLookup(new Event('submit'));
    expect(dictionary.lookup).toHaveBeenCalledWith('Learning');
    expect(component.lookupStatus()).toBe('found');
    fixture.detectChanges();
    const definitionPanel = (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLElement>('.definition-panel');
    expect(definitionPanel).not.toBeNull();
    expect(getComputedStyle(definitionPanel as HTMLElement).position).toBe('absolute');
  });

  it('keeps PDF.js-created text transparent and absolutely aligned over the canvas', async () => {
    await create();
    await vi.waitFor(() => expect(component.status()).toBe('ready'));
    fixture.detectChanges();

    const span = (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLElement>('.textLayer span');
    expect(span).not.toBeNull();

    const style = getComputedStyle(span as HTMLElement);
    expect(style.position).toBe('absolute');
    expect(style.color).toBe('rgba(0, 0, 0, 0)');
    expect(style.whiteSpace).toBe('pre');
    expect(style.userSelect).toBe('text');
  });

  it('keeps manual tools available when a page has no selectable text', async () => {
    loader.hasText = false;
    await create();
    await vi.waitFor(() => expect(component.status()).toBe('ready'));
    fixture.detectChanges();
    expect(component.textAvailable()).toBe(false);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('OCR is not available');
    const noteSpy = vi.fn();
    component.noteRequested.subscribe(noteSpy);
    component.addManualNote();
    expect(noteSpy).toHaveBeenCalledWith({ attachmentId: 9, pageNumber: 1, text: '' });
  });

  it('ends dictionary loading for provider failures without inventing a definition', async () => {
    dictionary.lookup.mockReturnValueOnce(throwError(() => new Error('offline')) as never);
    await create();
    component.openManualLookup();
    component.updateManualWord({ target: { value: 'Learning' } } as unknown as Event);
    component.submitManualLookup(new Event('submit'));
    expect(component.lookupStatus()).toBe('error');
    expect(component.lookupResult()).toBeNull();
  });

  it('shows an unavailable state, ends loading, and retries explicitly', async () => {
    loader.shouldFail = true;
    await create();

    expect(component.status()).toBe('error');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Preview unavailable');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Retry preview');
    expect(loader.calls).toBe(1);

    fixture.detectChanges();
    expect(loader.calls).toBe(1);
    loader.shouldFail = false;
    component.retry();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(loader.calls).toBe(2);
    expect(component.status()).toBe('ready');
  });

  it('rejects non-allowlisted URLs before loading PDF.js', async () => {
    await create('https://example.com/untrusted.pdf');

    expect(component.status()).toBe('error');
    expect(component.errorMessage()).toContain('not from an approved');
    expect(loader.calls).toBe(0);
  });

  it('destroys the old document and reloads when the URL changes', async () => {
    await create();
    fixture.componentRef.setInput(
      'url',
      'https://res.cloudinary.com/revisee/raw/upload/other.pdf',
    );
    fixture.detectChanges();
    await fixture.whenStable();

    expect(loader.destroy).toHaveBeenCalled();
    expect(loader.calls).toBe(2);
    expect(component.pageNumber()).toBe(1);
  });

  it('enters and exits native full screen with accessible state', async () => {
    const originalRequest = Object.getOwnPropertyDescriptor(
      Element.prototype,
      'requestFullscreen',
    );
    const originalExit = Object.getOwnPropertyDescriptor(document, 'exitFullscreen');
    const originalElement = Object.getOwnPropertyDescriptor(document, 'fullscreenElement');
    const requestFullscreen = vi.fn(() => Promise.resolve());
    const exitFullscreen = vi.fn(() => Promise.resolve());
    Object.defineProperty(Element.prototype, 'requestFullscreen', {
      configurable: true,
      value: requestFullscreen,
    });
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: null,
    });

    try {
      await create();
      const viewer = (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLElement>('.pdf-viewer');
      const button = (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLButtonElement>('.fullscreen-button');
      expect(button?.disabled).toBe(false);
      expect(button?.getAttribute('aria-label')).toBe('View PDF in full screen');

      await component.toggleFullscreen();
      expect(requestFullscreen).toHaveBeenCalledTimes(1);
      Object.defineProperty(document, 'fullscreenElement', {
        configurable: true,
        value: viewer,
      });
      document.dispatchEvent(new Event('fullscreenchange'));
      fixture.detectChanges();
      expect(component.fullscreen()).toBe(true);
      expect(button?.getAttribute('aria-label')).toBe('Exit full screen PDF view');

      const noteForm = new FormGroup({
        sourceExcerpt: new FormControl('Selected passage', { nonNullable: true }),
        noteText: new FormControl('My note', { nonNullable: true }),
      });
      fixture.componentRef.setInput('noteForm', noteForm);
      fixture.componentRef.setInput('noteEditorOpen', true);
      fixture.componentRef.setInput('noteEditorTitle', 'Study notes · Page 1');
      fixture.detectChanges();
      const noteEditor = (fixture.nativeElement as HTMLElement)
        .querySelector<HTMLElement>('.pdf-note-editor');
      expect(noteEditor).not.toBeNull();
      expect(viewer?.contains(noteEditor)).toBe(true);
      expect(document.fullscreenElement?.contains(noteEditor)).toBe(true);
      expect(noteEditor?.textContent).toContain('Study notes · Page 1');

      const saveSpy = vi.fn();
      component.noteSaveRequested.subscribe(saveSpy);
      noteEditor?.querySelector('form')?.dispatchEvent(new Event('submit'));
      expect(saveSpy).toHaveBeenCalledTimes(1);

      await component.toggleFullscreen();
      expect(exitFullscreen).toHaveBeenCalledTimes(1);
    } finally {
      if (originalRequest) Object.defineProperty(Element.prototype, 'requestFullscreen', originalRequest);
      else Reflect.deleteProperty(Element.prototype, 'requestFullscreen');
      if (originalExit) Object.defineProperty(document, 'exitFullscreen', originalExit);
      else Reflect.deleteProperty(document, 'exitFullscreen');
      if (originalElement) Object.defineProperty(document, 'fullscreenElement', originalElement);
      else Reflect.deleteProperty(document, 'fullscreenElement');
    }
  });
});
