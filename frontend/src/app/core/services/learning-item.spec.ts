import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { LearningItem, LearningItemResponse } from './learning-item';

const response: LearningItemResponse = {
  message: 'Learning item retrieved successfully.',
  data: {
    id: 12,
    title: 'Cell biology',
    description_text: '<p>Real saved notes</p>',
    labels: 'Biology, Science',
    image_urls: null,
    pdf_urls: null,
    pdf_resources: [],
    first_image_url: null,
    image_count: 0,
    pdf_count: 0,
    theory: null,
    key_points: [],
    questions: [],
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-02T10:00:00Z',
    hours_ago: 24,
  },
};

describe('LearningItem service', () => {
  let service: LearningItem;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(LearningItem);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the owned learning-item detail route', () => {
    let actual: LearningItemResponse | undefined;
    service.getLearningItem(12, { localLoading: true }).subscribe((value) => { actual = value; });
    const request = http.expectOne(`${environment.apiUrl}/learning-item/12`);
    expect(request.request.method).toBe('GET');
    request.flush(response);
    expect(actual).toEqual(response);
  });

  it('normalizes nullable or missing collections before components receive them', () => {
    let actual: LearningItemResponse | undefined;
    service.getLearningItem(12).subscribe((value) => { actual = value; });
    const request = http.expectOne(`${environment.apiUrl}/learning-item/12`);
    request.flush({
      ...response,
      data: {
        ...response.data,
        key_points: null,
        questions: null,
        labels: undefined,
        image_urls: undefined,
        pdf_urls: undefined,
      },
    });

    expect(actual?.data.key_points).toEqual([]);
    expect(actual?.data.questions).toEqual([]);
    expect(actual?.data.labels).toBeNull();
    expect(actual?.data.image_urls).toBeNull();
    expect(actual?.data.pdf_urls).toBeNull();
  });

  it('routes malformed response envelopes through the Observable error channel', () => {
    let receivedError: unknown;
    service.getLearningItem(12).subscribe({ error: (error: unknown) => { receivedError = error; } });
    const request = http.expectOne(`${environment.apiUrl}/learning-item/12`);
    request.flush({ message: 'ok', data: {} });

    expect(receivedError).toBeInstanceOf(TypeError);
  });

  it('uses the authenticated generate contract including learning_item_id', () => {
    service.generateRevisionContent(12, 'Cell biology', 'Cell notes').subscribe();
    const request = http.expectOne(`${environment.apiUrl}/generate`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      learning_item_id: 12,
      title: 'Cell biology',
      description: 'Cell notes',
    });
    request.flush({ message: 'Revision content generated successfully.' });
  });

  it('preserves the stored original PDF filename from the detail contract', () => {
    let actual: LearningItemResponse | undefined;
    service.getLearningItem(12).subscribe((value) => { actual = value; });
    const request = http.expectOne(`${environment.apiUrl}/learning-item/12`);
    request.flush({
      ...response,
      data: {
        ...response.data,
        pdf_resources: [{
          id: 9,
          url: 'https://res.cloudinary.com/revisee/raw/upload/generated-id.pdf',
          original_filename: 'Operating Systems Notes.pdf',
        }],
      },
    });

    expect(actual?.data.pdf_resources).toEqual([{
      id: 9,
      url: 'https://res.cloudinary.com/revisee/raw/upload/generated-id.pdf',
      original_filename: 'Operating Systems Notes.pdf',
    }]);
  });

  it('creates only a manual question through the owned-item contract', () => {
    const payload = { question: 'Question?', option_a: 'A', option_b: 'B', option_c: 'C', option_d: 'D', correct_option: 'A' as const, explanation: 'Explanation', difficulty: 2, expected_time_seconds: 30 };
    service.createQuestion(12, payload).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/learning-items/12/questions`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush({ message: 'Question added', question_id: 4 });
  });

  it('uses the append-only generated-question contract with explicit provider choice', () => {
    const payload = { generation_source: 'PERSONAL' as const, credential_id: 4, personal_remarks: 'Use examples', question_count: 5 };
    service.generateQuestions(12, payload).subscribe();
    const request = http.expectOne(`${environment.apiUrl}/learning-items/12/generated-questions`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);
    request.flush({ message: 'Questions generated and appended', status: 'COMPLETED', requested_count: 5, saved_count: 5, duplicate_count: 0 });
  });

  it('uses narrow authenticated PDF-note CRUD contracts', () => {
    service.listPdfNotes(12).subscribe();
    expect(http.expectOne(`${environment.apiUrl}/learning-items/12/pdf-notes`).request.method).toBe('GET');

    const create = { media_id: 4, page_number: 2, source_excerpt: 'Source', note_text: 'Mine' };
    service.createPdfNote(12, create).subscribe();
    const createRequest = http.expectOne(`${environment.apiUrl}/learning-items/12/pdf-notes`);
    expect(createRequest.request.method).toBe('POST');
    expect(createRequest.request.body).toEqual(create);

    const update = { source_excerpt: null, note_text: 'Revised' };
    service.updatePdfNote(12, 7, update).subscribe();
    const updateRequest = http.expectOne(`${environment.apiUrl}/learning-items/12/pdf-notes/7`);
    expect(updateRequest.request.method).toBe('PATCH');
    expect(updateRequest.request.body).toEqual(update);

    service.deletePdfNote(12, 7).subscribe();
    expect(http.expectOne(`${environment.apiUrl}/learning-items/12/pdf-notes/7`).request.method).toBe('DELETE');
  });
});
