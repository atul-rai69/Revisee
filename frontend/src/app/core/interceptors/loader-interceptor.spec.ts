import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { LoaderService } from '../services/loader.service';
import { loaderInterceptor } from './loader-interceptor';

describe('loaderInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  let loader: LoaderService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([loaderInterceptor])), provideHttpClientTesting()],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    loader = TestBed.inject(LoaderService);
  });

  afterEach(() => http.verify());

  it('remains visible until concurrent requests finish, including errors', () => {
    client.get('/first').subscribe();
    client.get('/second').subscribe({ error: () => undefined });
    const first = http.expectOne('/first');
    const second = http.expectOne('/second');
    expect(loader.isLoading()).toBe(true);
    first.flush({ ok: true });
    expect(loader.isLoading()).toBe(true);
    second.flush({ detail: 'failed' }, { status: 500, statusText: 'Server Error' });
    expect(loader.isLoading()).toBe(false);
  });
});
