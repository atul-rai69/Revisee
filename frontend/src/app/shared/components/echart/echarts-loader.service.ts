import { Injectable } from '@angular/core';

export type EChartsRuntime = typeof import('./echarts-runtime').echarts;

@Injectable({ providedIn: 'root' })
export class EChartsLoaderService {
  load(): Promise<EChartsRuntime> {
    return import('./echarts-runtime').then((runtime) => runtime.echarts);
  }
}
