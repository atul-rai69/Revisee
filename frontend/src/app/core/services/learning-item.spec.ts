import { TestBed } from '@angular/core/testing';

import { LearningItem } from './learning-item';

describe('LearningItem', () => {
  let service: LearningItem;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(LearningItem);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
