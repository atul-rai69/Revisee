import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Canvas } from './canvas';
import { vi } from 'vitest';

describe('Canvas', () => {
  let component: Canvas;
  let fixture: ComponentFixture<Canvas>;

  beforeEach(async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
      stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(), save: vi.fn(), restore: vi.fn(),
      translate: vi.fn(), rotate: vi.fn(), fillText: vi.fn(),
      set strokeStyle(_value: string) {}, set fillStyle(_value: string) {},
      set lineWidth(_value: number) {}, set lineCap(_value: CanvasLineCap) {},
      set font(_value: string) {}, set textAlign(_value: CanvasTextAlign) {},
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    await TestBed.configureTestingModule({
      imports: [Canvas]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Canvas);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  afterEach(() => vi.restoreAllMocks());

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
