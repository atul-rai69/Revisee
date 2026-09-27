import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { DashboardService } from '../../core/services/dashboard-service';
import { LearningItemRecencyService } from '../../core/services/learning-item-recency.service';
import { LearningItem } from '../../core/services/learning-item';
import { ToasterService } from '../../core/services/toaster.service';
import { Library } from './library';

class FakeDashboardService {
  result = of({ message: 'ok', data: [
    { id: 1, title: 'Cell biology', description_text: '<p>Cells</p>', labels: 'Biology, Science', first_image_url: null, image_count: 1, pdf_count: 0, hours_ago: 2 },
    { id: 2, title: 'TypeScript', description_text: '<p>Types</p>', labels: 'Programming', first_image_url: null, image_count: 0, pdf_count: 1, hours_ago: 3 },
  ] });
  getLearningItemSummary() { return this.result; }
}
class FakeLearningItem { deleteLearningItem = vi.fn(() => of(null)); }
class FakeRecencyService { exploredAt = vi.fn(() => null); remove = vi.fn(); }
class FakeToaster { success = vi.fn(); error = vi.fn(); }
class FakeRouter { navigate = vi.fn().mockResolvedValue(true); }

describe('Library', () => {
  let fixture: ComponentFixture<Library>;
  let component: Library;
  let dashboard: FakeDashboardService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [Library], providers: [
      { provide: DashboardService, useClass: FakeDashboardService },
      { provide: LearningItem, useClass: FakeLearningItem },
      { provide: LearningItemRecencyService, useClass: FakeRecencyService },
      { provide: ToasterService, useClass: FakeToaster },
      { provide: Router, useClass: FakeRouter },
    ] }).compileComponents();
    dashboard = TestBed.inject(DashboardService) as unknown as FakeDashboardService;
    fixture = TestBed.createComponent(Library);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('shows the complete owned collection and available Topic filters', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Cell biology');
    expect(text).toContain('TypeScript');
    expect(text).toContain('Biology');
    expect(fixture.nativeElement.querySelectorAll('.library-card')).toHaveLength(2);
  });

  it('searches content and filters by Topic without changing source data', () => {
    component.searchQuery.set('types');
    fixture.detectChanges();
    expect(component.filteredItems().map((item) => item.id)).toEqual([2]);
    component.searchQuery.set('');
    component.topicFilter.set('Science');
    fixture.detectChanges();
    expect(component.filteredItems().map((item) => item.id)).toEqual([1]);
    expect(component.items()).toHaveLength(2);
  });

  it('requires confirmation before deletion and removes recency after success', () => {
    const learningItems = TestBed.inject(LearningItem) as unknown as FakeLearningItem;
    const recency = TestBed.inject(LearningItemRecencyService) as unknown as FakeRecencyService;
    component.requestDelete(1);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-confirmation-dialog')).toBeTruthy();
    expect(learningItems.deleteLearningItem).not.toHaveBeenCalled();
    component.confirmDelete();
    fixture.detectChanges();
    expect(learningItems.deleteLearningItem).toHaveBeenCalledWith(1);
    expect(recency.remove).toHaveBeenCalledWith(1);
    expect(component.items().map((item) => item.id)).toEqual([2]);
  });

  it('shows retry and no-results states honestly', () => {
    dashboard.result = throwError(() => new Error('offline')) as typeof dashboard.result;
    component.loadItems();
    fixture.detectChanges();
    expect(component.loading()).toBe(false);
    expect(component.error()).toBe(true);
    component.error.set(false);
    component.searchQuery.set('missing');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('No matching material');
  });
});
