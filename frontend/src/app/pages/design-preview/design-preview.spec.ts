import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DesignPreview } from './design-preview';

describe('DesignPreview', () => {
  let component: DesignPreview;
  let fixture: ComponentFixture<DesignPreview>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DesignPreview]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DesignPreview);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
