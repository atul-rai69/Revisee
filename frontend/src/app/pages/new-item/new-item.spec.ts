import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NEVER } from 'rxjs';

import { NewItem } from './new-item';
import { LabelService } from '../../core/services/label-service';
import { LearningItem } from '../../core/services/learning-item';

class FakeLabelService { getLabels() { return NEVER; } }
class FakeLearningItemService {}

describe('NewItem', () => {
  let component: NewItem;
  let fixture: ComponentFixture<NewItem>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewItem],
      providers: [
        { provide: LabelService, useClass: FakeLabelService },
        { provide: LearningItem, useClass: FakeLearningItemService },
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(NewItem);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
