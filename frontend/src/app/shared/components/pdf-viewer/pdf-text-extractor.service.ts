import { Injectable } from '@angular/core';
import type { PDFDocumentLoadingTask } from 'pdfjs-dist';
import { PdfJsLoaderService } from './pdfjs-loader.service';

export interface ExtractedPdfPage {
  page_number: number;
  text: string;
  has_usable_text: boolean;
}

export interface PdfTextExtractionResult {
  pageCount: number;
  pages: ExtractedPdfPage[];
  scannedPageNumbers: number[];
  totalCharacters: number;
}

export interface PdfTextExtractionOptions {
  firstPage?: number;
  lastPage?: number;
  signal?: AbortSignal;
  onProgress?: (completed: number, total: number) => void;
}

export type PdfTextExtractionErrorCode =
  | 'INVALID_FILE_TYPE'
  | 'FILE_SIZE'
  | 'INVALID_RANGE'
  | 'PAGE_LIMIT'
  | 'CHARACTER_LIMIT'
  | 'UNAVAILABLE';

export class PdfTextExtractionError extends Error {
  constructor(readonly code: PdfTextExtractionErrorCode, message: string) {
    super(message);
  }
}

export const MAX_PDF_QUESTION_FILE_BYTES = 10 * 1024 * 1024;
const MAX_PAGES = 50;
const MAX_PAGE_CHARACTERS = 20_000;
const MAX_TOTAL_CHARACTERS = 120_000;
const MIN_USABLE_CHARACTERS = 12;

export function validatePdfQuestionFile(file: File): void {
  if (file.name.length > 255 || file.type.toLocaleLowerCase() !== 'application/pdf'
    || !file.name.toLocaleLowerCase().endsWith('.pdf')) {
    throw new PdfTextExtractionError(
      'INVALID_FILE_TYPE',
      'Choose a PDF file with the .pdf extension and application/pdf type.',
    );
  }
  if (file.size <= 0 || file.size > MAX_PDF_QUESTION_FILE_BYTES) {
    throw new PdfTextExtractionError('FILE_SIZE', 'Choose a non-empty PDF no larger than 10 MB.');
  }
}

@Injectable({ providedIn: 'root' })
export class PdfTextExtractorService {
  constructor(private readonly loader: PdfJsLoaderService) {}

  async inspect(file: File, signal?: AbortSignal): Promise<number> {
    validatePdfQuestionFile(file);
    let loadingTask: PDFDocumentLoadingTask | null = null;
    let abortHandler: (() => void) | null = null;
    const objectUrl = URL.createObjectURL(file);
    try {
      this.throwIfCancelled(signal);
      const pdfjs = await this.loader.load();
      this.throwIfCancelled(signal);
      loadingTask = pdfjs.getDocument(this.documentOptions(objectUrl));
      abortHandler = () => { void loadingTask?.destroy(); };
      signal?.addEventListener('abort', abortHandler, { once: true });
      const documentProxy = await loadingTask.promise;
      this.throwIfCancelled(signal);
      return documentProxy.numPages;
    } catch (error: unknown) {
      if (error instanceof PdfTextExtractionError || this.isAbort(error)) throw error;
      throw new PdfTextExtractionError('UNAVAILABLE', 'This PDF could not be opened. Choose another file.');
    } finally {
      if (abortHandler) signal?.removeEventListener('abort', abortHandler);
      if (loadingTask) await loadingTask.destroy().catch(() => undefined);
      URL.revokeObjectURL(objectUrl);
    }
  }

  async extract(file: File, options: PdfTextExtractionOptions = {}): Promise<PdfTextExtractionResult> {
    validatePdfQuestionFile(file);
    let loadingTask: PDFDocumentLoadingTask | null = null;
    let abortHandler: (() => void) | null = null;
    const objectUrl = URL.createObjectURL(file);
    try {
      this.throwIfCancelled(options.signal);
      const pdfjs = await this.loader.load();
      this.throwIfCancelled(options.signal);
      loadingTask = pdfjs.getDocument(this.documentOptions(objectUrl));
      abortHandler = () => { void loadingTask?.destroy(); };
      options.signal?.addEventListener('abort', abortHandler, { once: true });
      const documentProxy = await loadingTask.promise;
      this.throwIfCancelled(options.signal);

      const firstPage = options.firstPage ?? 1;
      const lastPage = options.lastPage ?? documentProxy.numPages;
      if (!Number.isInteger(firstPage) || !Number.isInteger(lastPage) || firstPage < 1
        || lastPage < firstPage || lastPage > documentProxy.numPages) {
        throw new PdfTextExtractionError('INVALID_RANGE', `Choose pages between 1 and ${documentProxy.numPages}.`);
      }
      const selectedCount = lastPage - firstPage + 1;
      if (selectedCount > MAX_PAGES) {
        throw new PdfTextExtractionError('PAGE_LIMIT', `Select no more than ${MAX_PAGES} pages at a time.`);
      }

      const pages: ExtractedPdfPage[] = [];
      const scannedPageNumbers: number[] = [];
      let totalCharacters = 0;
      for (let pageNumber = firstPage; pageNumber <= lastPage; pageNumber += 1) {
        this.throwIfCancelled(options.signal);
        const page = await documentProxy.getPage(pageNumber);
        const textContent = await page.getTextContent();
        this.throwIfCancelled(options.signal);
        const text = this.normalizePageItems(textContent.items);
        if (text.length > MAX_PAGE_CHARACTERS) {
          throw new PdfTextExtractionError('CHARACTER_LIMIT', `Page ${pageNumber} contains more text than this workflow can process safely.`);
        }
        totalCharacters += text.length;
        if (totalCharacters > MAX_TOTAL_CHARACTERS) {
          throw new PdfTextExtractionError('CHARACTER_LIMIT', 'The selected pages contain too much text. Choose a smaller page range.');
        }
        const hasUsableText = text.replace(/\s/gu, '').length >= MIN_USABLE_CHARACTERS;
        if (!hasUsableText) scannedPageNumbers.push(pageNumber);
        pages.push({ page_number: pageNumber, text, has_usable_text: hasUsableText });
        options.onProgress?.(pageNumber - firstPage + 1, selectedCount);
      }
      return { pageCount: documentProxy.numPages, pages, scannedPageNumbers, totalCharacters };
    } catch (error: unknown) {
      if (error instanceof PdfTextExtractionError || this.isAbort(error)) throw error;
      throw new PdfTextExtractionError('UNAVAILABLE', 'The PDF text could not be read. Choose another file or try again.');
    } finally {
      if (abortHandler) options.signal?.removeEventListener('abort', abortHandler);
      if (loadingTask) await loadingTask.destroy().catch(() => undefined);
      URL.revokeObjectURL(objectUrl);
    }
  }

  private documentOptions(objectUrl: string): Record<string, unknown> {
    return {
      url: objectUrl,
      withCredentials: false,
      cMapUrl: this.loader.assetUrl('cmaps/'),
      cMapPacked: true,
      iccUrl: this.loader.assetUrl('iccs/'),
      standardFontDataUrl: this.loader.assetUrl('standard_fonts/'),
      wasmUrl: this.loader.assetUrl('wasm/'),
    };
  }

  private normalizePageItems(items: readonly unknown[]): string {
    const lines: string[] = [];
    let line = '';
    for (const item of items) {
      if (!this.isTextItem(item)) continue;
      const value = item.str.replace(/[\t\f\v ]+/gu, ' ').trim();
      if (value) line = line ? `${line} ${value}` : value;
      if (item.hasEOL) {
        if (line) lines.push(line);
        line = '';
      }
    }
    if (line) lines.push(line);
    return lines.join('\n').replace(/\n{3,}/gu, '\n\n').trim();
  }

  private isTextItem(value: unknown): value is { str: string; hasEOL: boolean } {
    return typeof value === 'object' && value !== null && 'str' in value
      && typeof value.str === 'string' && 'hasEOL' in value && typeof value.hasEOL === 'boolean';
  }

  private throwIfCancelled(signal?: AbortSignal): void {
    if (signal?.aborted) throw new DOMException('PDF extraction cancelled.', 'AbortError');
  }

  private isAbort(error: unknown): boolean {
    return error instanceof DOMException && error.name === 'AbortError';
  }
}
