import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Playground } from './playground';
import { vi } from 'vitest';

describe('Playground', () => {
  let component: Playground;
  let fixture: ComponentFixture<Playground>;

  beforeEach(async () => {
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    await TestBed.configureTestingModule({
      imports: [Playground]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Playground);
    component = fixture.componentInstance;
  });

  afterEach(() => vi.restoreAllMocks());

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
