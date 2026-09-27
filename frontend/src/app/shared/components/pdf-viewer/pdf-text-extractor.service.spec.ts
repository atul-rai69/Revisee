import { TestBed } from '@angular/core/testing';
import { PdfJsLoaderService } from './pdfjs-loader.service';
import {
  MAX_PDF_QUESTION_FILE_BYTES,
  PdfTextExtractionError,
  PdfTextExtractorService,
  validatePdfQuestionFile,
} from './pdf-text-extractor.service';

class FakeLoader {
  readonly destroy = vi.fn(() => Promise.resolve());
  readonly pages = new Map<number, unknown[]>([
    [1, [
      { str: 'Question 1?', hasEOL: true },
      { str: 'A. First', hasEOL: true },
      { str: 'B. Second', hasEOL: false },
    ]],
    [2, []],
  ]);

  load() {
    return Promise.resolve({
      getDocument: () => ({
        promise: Promise.resolve({
          numPages: 2,
          getPage: (page: number) => Promise.resolve({
            getTextContent: () => Promise.resolve({ items: this.pages.get(page) ?? [] }),
          }),
        }),
        destroy: this.destroy,
      }),
    });
  }

  assetUrl(path: string): string { return `/assets/pdfjs/${path}`; }
}

function pdfFile(name = 'questions.pdf', size = 100): File {
  return new File([new Uint8Array(size)], name, { type: 'application/pdf' });
}

describe('PdfTextExtractorService', () => {
  let service: PdfTextExtractorService;
  let loader: FakeLoader;
  let revokeObjectUrl: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:local-pdf');
    revokeObjectUrl = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    TestBed.configureTestingModule({
      providers: [{ provide: PdfJsLoaderService, useClass: FakeLoader }],
    });
    service = TestBed.inject(PdfTextExtractorService);
    loader = TestBed.inject(PdfJsLoaderService) as unknown as FakeLoader;
  });

  afterEach(() => vi.restoreAllMocks());

  it('inspects and extracts a local PDF while releasing every object URL', async () => {
    const file = pdfFile();
    await expect(service.inspect(file)).resolves.toBe(2);
    const progress = vi.fn();
    const result = await service.extract(file, { onProgress: progress });

    expect(result.pageCount).toBe(2);
    expect(result.pages[0].text).toBe('Question 1?\nA. First\nB. Second');
    expect(result.scannedPageNumbers).toEqual([2]);
    expect(progress).toHaveBeenLastCalledWith(2, 2);
    expect(loader.destroy).toHaveBeenCalledTimes(2);
    expect(revokeObjectUrl).toHaveBeenCalledTimes(2);
  });

  it('rejects invalid file types and oversized PDFs before PDF.js runs', () => {
    const wrongType = new File(['plain text'], 'questions.pdf', { type: 'text/plain' });
    const wrongExtension = new File(['pdf'], 'questions.txt', { type: 'application/pdf' });
    const oversized = pdfFile('large.pdf', MAX_PDF_QUESTION_FILE_BYTES + 1);

    expect(() => validatePdfQuestionFile(wrongType)).toThrow(PdfTextExtractionError);
    expect(() => validatePdfQuestionFile(wrongExtension)).toThrow(PdfTextExtractionError);
    expect(() => validatePdfQuestionFile(oversized)).toThrowError(/10 MB/);
  });

  it('validates page ranges and always releases the PDF task and object URL', async () => {
    await expect(service.extract(pdfFile(), { firstPage: 2, lastPage: 3 }))
      .rejects.toMatchObject({ code: 'INVALID_RANGE' } satisfies Partial<PdfTextExtractionError>);
    expect(loader.destroy).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledOnce();
  });

  it('cancels stale extraction and releases its object URL', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(service.extract(pdfFile(), { signal: controller.signal }))
      .rejects.toMatchObject({ name: 'AbortError' });
    expect(revokeObjectUrl).toHaveBeenCalledOnce();
  });
});
