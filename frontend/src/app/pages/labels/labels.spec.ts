import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Labels } from './labels';

describe('Labels', () => {
  let component: Labels;
  let fixture: ComponentFixture<Labels>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Labels]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Labels);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
