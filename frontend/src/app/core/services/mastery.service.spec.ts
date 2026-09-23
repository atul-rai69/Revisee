import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { MasteryService } from './mastery.service';

describe('MasteryService', () => {
  let service: MasteryService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(MasteryService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  it('requests a user-owned paginated entity view', () => {
    service.getAnalytics('LABEL', 20, 40).subscribe();
    const request = http.expectOne((candidate) => candidate.url === `${environment.apiUrl}/mastery/analytics`);
    expect(request.request.params.get('entity_type')).toBe('LABEL');
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('offset')).toBe('40');
    request.flush({ entity_type: 'LABEL', minimum_attempts: 3, offset: 40, limit: 20, total: 0, items: [] });
  });

  for (const sessionLimit of [7, 30, 50] as const) {
    it(`requests the authoritative ${sessionLimit}-session analytics window`, () => {
      service.getRevisionAnalytics(sessionLimit).subscribe();
      const request = http.expectOne(
        (candidate) => candidate.url === `${environment.apiUrl}/analytics/revision-activity`,
      );
      expect(request.request.params.keys()).toEqual(['session_limit']);
      expect(request.request.params.get('session_limit')).toBe(String(sessionLimit));
      expect(request.request.method).toBe('GET');
      request.flush({ completed_session_count: 0, activity: [], requested_session_limit: sessionLimit, sessions_used: 0, measured_learning_item_count: 0, weak_area_ready: false, minimum_attempts: 3, topic_attribution: 'CURRENT_LEARNING_ITEM_TOPICS', attribution_note: '', topic_practice: [] });
    });
  }

  it('loads an authoritative weak-area classification when readiness allows it', () => {
    service.getWeakAreas('DUE_REVIEW', 6).subscribe();
    const request = http.expectOne((candidate) => candidate.url === `${environment.apiUrl}/weak-areas`);
    expect(request.request.params.get('entity_type')).toBe('LEARNING_ITEM');
    expect(request.request.params.get('classification')).toBe('DUE_REVIEW');
    expect(request.request.params.get('limit')).toBe('6');
    request.flush({ items: [], pagination: { offset: 0, limit: 6, total: 0 } });
  });
});
