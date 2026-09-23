import { isPlatformBrowser } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  PLATFORM_ID,
  SimpleChanges,
  ViewChild,
  inject,
} from '@angular/core';
import type { EChartsCoreOption, EChartsType } from 'echarts/core';
import { EChartsLoaderService } from './echarts-loader.service';

@Component({
  selector: 'app-echart',
  template: '<div #chart class="chart" role="img" tabindex="0" [attr.aria-label]="ariaLabel"></div>',
  styles: ':host,.chart{display:block;width:100%;height:100%;min-height:inherit}',
})
export class EChart implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) option!: EChartsCoreOption;
  @Input({ required: true }) ariaLabel = 'Analytics chart';
  @ViewChild('chart', { static: true }) private chartElement!: ElementRef<HTMLDivElement>;

  private readonly loader = inject(EChartsLoaderService);
  private readonly platformId = inject(PLATFORM_ID);
  private chart: EChartsType | null = null;
  private intersectionObserver: IntersectionObserver | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private destroyed = false;
  private loading = false;

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    if (typeof IntersectionObserver === 'undefined') {
      void this.initialize();
      return;
    }
    this.intersectionObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        this.intersectionObserver?.disconnect();
        this.intersectionObserver = null;
        void this.initialize();
      }
    }, { rootMargin: '160px' });
    this.intersectionObserver.observe(this.chartElement.nativeElement);
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['option'] && this.chart) this.chart.setOption(this.option, true);
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.intersectionObserver?.disconnect();
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
    this.chart = null;
  }

  private async initialize(): Promise<void> {
    if (this.loading || this.chart || this.destroyed) return;
    this.loading = true;
    try {
      const runtime = await this.loader.load();
      if (this.destroyed) return;
      this.chart = runtime.init(this.chartElement.nativeElement, undefined, {
        renderer: 'canvas',
      });
      this.chart.setOption(this.option, true);
      if (typeof ResizeObserver !== 'undefined') {
        this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
        this.resizeObserver.observe(this.chartElement.nativeElement);
      }
    } finally {
      this.loading = false;
    }
  }
}
