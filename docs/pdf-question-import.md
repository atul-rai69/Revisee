# PDF question import

## Scope and source lifecycle

This is a review-first question importer, not chat or semantic search. It does not use learning-item PDF attachments. The user selects a new local PDF specifically for this workflow at `/app/learning-items/:learningItemId/questions/import-pdf`.

PDF.js inspects and extracts the selected pages in the browser. Revisee does not upload the PDF to Cloudinary, add it to learning-item media, persist its binary, or store it in browser storage. Every temporary object URL and PDF loading task is released after inspection or extraction. Choosing another file, leaving the route, or cancelling stops stale work and discards in-memory text and unimported drafts.

Two modes are intentionally separate:

- **Extract existing questions** uses a deterministic browser parser first and does not invent questions. Optional AI-assisted parsing is an explicit user action.
- **Generate questions from PDF** sends bounded, page-aware passages to the selected Gemini provider and returns grounded drafts without saving them.

Only `POST /learning-items/{item_id}/pdf-questions/import` can insert reviewed questions.

## API contracts

- `POST /learning-items/{item_id}/pdf-question-drafts/generate`
- `POST /learning-items/{item_id}/pdf-questions/import`

Both bodies contain `source_filename` and bounded `source_pages`. They never accept a media ID, PDF URL, binary, or user ID. Authentication establishes the user, and the source/current and optional destination learning items must belong to that user.

## Runtime limits

- PDF MIME type `application/pdf` and `.pdf` extension
- 10 MB local file limit
- 50 selected pages per operation
- 20,000 extracted characters per page
- 120,000 extracted characters per request
- 10 Gemini drafts per request
- 25 drafts per import
- 2,000 focus-instruction characters
- Up to 12 evenly distributed source pages in one bounded Gemini prompt; the response reports the exact coverage pages

## Grounding and trust boundary

The backend treats browser-extracted text and the local filename as untrusted. It validates filename shape, item ownership, page-number uniqueness, field shapes, character totals, evidence excerpts, question validation, provider selection, BYOK ownership, and fingerprints. It never fetches a client-supplied URL.

Generated drafts must cite a submitted page and an excerpt found on that page after whitespace-only normalization. Unsupported citations, invalid options, invalid answers, malformed fields, and duplicate batch questions are omitted. Final import repeats evidence and ownership checks, reuses manual-question validation, reports existing duplicates, and inserts accepted questions in one transaction.

Because extraction occurs in the browser, the backend verifies evidence against submitted page text but cannot cryptographically prove that text came from the selected PDF binary. That limitation is accepted for this user-owned workflow and is disclosed in implementation documentation. PDF page/excerpt provenance remains draft-only, so no migration is required.

## Provider privacy

Deterministic extraction stays in the browser. Selected extracted text and optional focus instructions are sent to Gemini only for grounded generation or after the user explicitly chooses AI-assisted parsing. A failed personal-key request never falls back to the Revisee provider.

## Scanned PDFs and OCR

Pages without usable PDF text are detected and reported as requiring OCR, not as having no questions. OCR is not implemented.

Tesseract.js is Apache-2.0 licensed and can run in a browser worker, but it does not consume PDFs directly. A safe follow-up needs PDF.js page-to-image rendering, lazy self-hosted worker/WASM/language assets, strict page and resolution limits, sequential recognition, progress, cancellation, and mobile memory testing.

Official references:

- https://github.com/naptha/tesseract.js
- https://github.com/naptha/tesseract.js/blob/master/docs/performance.md
- https://github.com/naptha/tesseract.js/blob/master/docs/faq.md
