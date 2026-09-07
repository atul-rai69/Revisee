import { TestBed } from '@angular/core/testing';
import { LoaderService } from './loader.service';

describe('LoaderService', () => {
  it('reference-counts concurrent requests and never becomes negative', () => {
    const loader = TestBed.inject(LoaderService);
    loader.show();
    loader.show();
    expect(loader.isLoading()).toBe(true);
    loader.hide();
    expect(loader.isLoading()).toBe(true);
    loader.hide();
    expect(loader.isLoading()).toBe(false);
    loader.hide();
    expect(loader.isLoading()).toBe(false);
  });
});
