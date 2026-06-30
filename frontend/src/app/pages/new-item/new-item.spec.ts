import { ComponentFixture, TestBed } from '@angular/core/testing';

import { NewItem } from './new-item';

describe('NewItem', () => {
  let component: NewItem;
  let fixture: ComponentFixture<NewItem>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewItem]
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
