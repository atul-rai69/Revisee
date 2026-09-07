import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { SKIP_GLOBAL_LOADER } from '../interceptors/loader-interceptor';
import { DashboardService } from './dashboard-service';

describe('DashboardService', () => {
  let service: DashboardService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DashboardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the real dashboard summary contract', () => {
    service.getDashboardSummary({ localLoading: true }).subscribe((value) => expect(value.username).toBe('Atul'));
    const request = http.expectOne(`${environment.apiUrl}/dashboard/summary`);
    expect(request.request.method).toBe('GET');
    expect(request.request.context.get(SKIP_GLOBAL_LOADER)).toBe(true);
    request.flush({ username: 'Atul', total_items: 3, total_labels: 2, login_streak: 4 });
  });

  it('loads nullable learning-item summary fields without changing the API shape', () => {
    service.getLearningItemSummary({ localLoading: true }).subscribe((value) => {
      expect(value.data[0].labels).toBeNull();
      expect(value.data[0].first_image_url).toBeNull();
    });
    const request = http.expectOne(`${environment.apiUrl}/dashboard/learning-items-summary`);
    request.flush({
      message: 'ok',
      data: [{ id: 1, title: 'Notes', description_text: null, labels: null, first_image_url: null, image_count: 0, pdf_count: 0, hours_ago: 2 }],
    });
  });
});
