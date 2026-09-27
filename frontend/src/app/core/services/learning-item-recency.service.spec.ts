import { TestBed } from '@angular/core/testing';
import { LearningItemRecencyService } from './learning-item-recency.service';

describe('LearningItemRecencyService', () => {
  let service: LearningItemRecencyService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    service = TestBed.inject(LearningItemRecencyService);
  });

  afterEach(() => localStorage.clear());

  it('records the latest exploration without storing learning content', () => {
    service.markExplored(7, 1000);
    service.markExplored(7, 2000);
    expect(service.exploredAt(7)).toBe(2000);
    expect(localStorage.getItem('revisee.learning-item-exploration.v1')).not.toContain('title');
  });

  it('removes stale entries after an item is deleted', () => {
    service.markExplored(7, 1000);
    service.remove(7);
    expect(service.exploredAt(7)).toBeNull();
  });
});
