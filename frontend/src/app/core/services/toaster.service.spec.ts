import { TestBed } from '@angular/core/testing';
import { ToasterService } from './toaster.service';

describe('ToasterService', () => {
  it('creates all accessible feedback variants and removes them', () => {
    const toaster = TestBed.inject(ToasterService);
    toaster.success('Saved', { duration: 0 });
    toaster.error('Failed', { duration: 0 });
    toaster.warning('Check answers', { duration: 0 });
    toaster.info('Resumed', { duration: 0 });
    expect(toaster.toasts().map((toast) => toast.type)).toEqual(['info', 'warning', 'error', 'success']);
    toaster.clear();
    expect(toaster.toasts()).toEqual([]);
  });
});
