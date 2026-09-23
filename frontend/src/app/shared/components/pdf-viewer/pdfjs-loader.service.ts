import { DOCUMENT } from '@angular/common';
import { Inject, Injectable } from '@angular/core';

export type PdfJsModule = typeof import('pdfjs-dist');

@Injectable({ providedIn: 'root' })
export class PdfJsLoaderService {
  private modulePromise: Promise<PdfJsModule> | null = null;

  constructor(@Inject(DOCUMENT) private readonly document: Document) {}

  load(): Promise<PdfJsModule> {
    this.modulePromise ??= import('pdfjs-dist').then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        'assets/pdfjs/pdf.worker.min.mjs',
        this.document.baseURI,
      ).href;
      return pdfjs;
    });
    return this.modulePromise;
  }

  assetUrl(path: string): string {
    return new URL(`assets/pdfjs/${path}`, this.document.baseURI).href;
  }
}
