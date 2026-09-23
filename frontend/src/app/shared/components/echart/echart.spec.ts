import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { EChart } from './echart';
import { EChartsLoaderService } from './echarts-loader.service';

describe('EChart', () => {
  let fixture: ComponentFixture<EChart>;
  const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() };
  const runtime = { init: vi.fn(() => chart) };

  beforeEach(async () => {
    vi.clearAllMocks();
    await TestBed.configureTestingModule({
      imports: [EChart],
      providers: [{ provide: EChartsLoaderService, useValue: { load: () => Promise.resolve(runtime) } }],
    }).compileComponents();
    fixture = TestBed.createComponent(EChart);
    fixture.componentRef.setInput('option', { series: [] });
    fixture.componentRef.setInput('ariaLabel', 'Revision activity');
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('initializes lazily and exposes an accessible chart description', () => {
    expect(runtime.init).toHaveBeenCalledTimes(1);
    expect(chart.setOption).toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('[role="img"]').getAttribute('aria-label')).toBe('Revision activity');
  });

  it('disposes the chart when removed', () => {
    fixture.destroy();
    expect(chart.dispose).toHaveBeenCalledTimes(1);
  });
});
