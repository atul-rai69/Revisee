import type { EChartsCoreOption } from 'echarts/core';
import type {
  MasteryAnalyticsItem,
  RevisionActivityPoint,
  TopicPracticePoint,
  WeakAreaItem,
} from '../../core/services/mastery.service';

const NAVY = '#071638';
const TEAL = '#147d73';
const TEAL_LIGHT = '#12bdae';
const AMBER = '#e9ad43';
const CORAL = '#df765e';
const GRID = '#dfe5df';
const MUTED = '#667270';
const TOPIC_COLORS = [TEAL, AMBER, CORAL, '#5967a8', '#789262'];

interface AxisTooltipParam {
  axisValue?: string | number;
  data?: unknown;
  seriesName?: string;
}

interface MasteryDatum {
  value: number;
  sessionId: number;
  recordedAt: string;
  attempts: number;
  correct: number;
}

function firstTooltipParam(value: unknown): AxisTooltipParam | null {
  if (Array.isArray(value)) return (value[0] as AxisTooltipParam | undefined) ?? null;
  return value && typeof value === 'object' ? value as AxisTooltipParam : null;
}

function compactDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(value));
}

function baseOption(reducedMotion: boolean): EChartsCoreOption {
  return {
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 420,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: NAVY },
    aria: { enabled: true, decal: { show: true } },
  };
}

export function revisionActivityOption(
  points: RevisionActivityPoint[],
  reducedMotion: boolean,
): EChartsCoreOption {
  const byDate = new Map(points.map((point) => [point.date, point]));
  return {
    ...baseOption(reducedMotion),
    color: [TEAL, CORAL],
    grid: { left: 46, right: 50, top: 28, bottom: 44 },
    legend: { bottom: 0, textStyle: { color: MUTED } },
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      formatter: (value: unknown) => {
        const key = String(firstTooltipParam(value)?.axisValue ?? '');
        const point = byDate.get(key);
        if (!point) return '';
        const accuracy = point.accuracy_percent === null ? 'Not available' : `${point.accuracy_percent}%`;
        return `${compactDate(point.date)}\nCompleted sessions: ${point.completed_session_count}\nCorrect / answered: ${point.correct_count} / ${point.answered_count}\nWeighted accuracy: ${accuracy}`;
      },
    },
    xAxis: {
      type: 'category',
      data: points.map((point) => point.date),
      axisLabel: { color: MUTED, hideOverlap: true, formatter: (value: string) => compactDate(value) },
      axisLine: { lineStyle: { color: GRID } },
    },
    yAxis: [
      { type: 'value', minInterval: 1, name: 'Sessions', axisLabel: { color: MUTED }, splitLine: { lineStyle: { color: GRID } } },
      { type: 'value', min: 0, max: 100, name: 'Accuracy', axisLabel: { color: MUTED, formatter: '{value}%' }, splitLine: { show: false } },
    ],
    series: [
      { name: 'Completed sessions', type: 'bar', barMaxWidth: 34, data: points.map((point) => point.completed_session_count), itemStyle: { borderRadius: [5, 5, 0, 0] } },
      { name: 'Weighted accuracy', type: 'line', yAxisIndex: 1, smooth: 0.25, symbolSize: 8, connectNulls: false, data: points.map((point) => point.accuracy_percent) },
    ],
  };
}

export function masteryGrowthOption(
  items: MasteryAnalyticsItem[],
  minimumAttempts: number,
  reducedMotion: boolean,
): EChartsCoreOption {
  const allPoints = items.flatMap((item) => item.trend.filter((point) => point.total_attempts >= minimumAttempts));
  const keys = [...new Set(allPoints.map((point) => `${point.recorded_at}|${point.session_id}`))]
    .sort((left, right) => left.localeCompare(right));
  const labels = new Map(keys.map((key) => [key, compactDate(key.split('|')[0])]));
  return {
    ...baseOption(reducedMotion),
    color: TOPIC_COLORS,
    grid: { left: 44, right: 18, top: 38, bottom: 48 },
    legend: { type: 'scroll', top: 0, textStyle: { color: MUTED } },
    tooltip: {
      trigger: 'item',
      renderMode: 'richText',
      formatter: (value: unknown) => {
        const param = firstTooltipParam(value);
        const datum = param?.data as MasteryDatum | undefined;
        if (!datum) return '';
        return `${param?.seriesName ?? 'Mastery'}\n${compactDate(datum.recordedAt)} · Session ${datum.sessionId}\nMastery: ${datum.value}%\nEvidence: ${datum.correct} correct from ${datum.attempts} attempts`;
      },
    },
    xAxis: { type: 'category', data: keys, axisLabel: { color: MUTED, formatter: (value: string) => labels.get(value) ?? value, hideOverlap: true }, axisLine: { lineStyle: { color: GRID } } },
    yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: MUTED, formatter: '{value}%' }, splitLine: { lineStyle: { color: GRID } } },
    series: items.map((item) => {
      const byKey = new Map(
        item.trend
          .filter((point) => point.total_attempts >= minimumAttempts)
          .map((point) => [`${point.recorded_at}|${point.session_id}`, {
            value: point.score_after,
            sessionId: point.session_id,
            recordedAt: point.recorded_at,
            attempts: point.total_attempts,
            correct: point.correct_attempts,
          } satisfies MasteryDatum]),
      );
      return {
        name: item.display_name,
        type: 'line',
        smooth: 0.25,
        symbol: 'circle',
        symbolSize: 8,
        connectNulls: false,
        data: keys.map((key) => byKey.get(key) ?? null),
      };
    }),
  };
}

export function individualMasteryOption(
  item: MasteryAnalyticsItem,
  minimumAttempts: number,
  reducedMotion: boolean,
): EChartsCoreOption {
  return masteryGrowthOption([item], minimumAttempts, reducedMotion);
}

export function topicPracticeBubbleOption(
  points: TopicPracticePoint[],
  reducedMotion: boolean,
): EChartsCoreOption {
  const lookup = new Map(points.map((point) => [point.topic_name, point]));
  return {
    ...baseOption(reducedMotion),
    color: [TEAL_LIGHT],
    grid: { left: 48, right: 24, top: 28, bottom: 45 },
    tooltip: {
      trigger: 'item',
      renderMode: 'richText',
      formatter: (value: unknown) => {
        const data = firstTooltipParam(value)?.data;
        const values = Array.isArray(data) ? data : [];
        const point = lookup.get(String(values[3] ?? ''));
        if (!point) return '';
        return `${point.topic_name}\nAttempts: ${point.attempt_count}\nCorrect: ${point.correct_count}\nAccuracy: ${point.accuracy_percent}%\nSessions practised: ${point.session_count}`;
      },
    },
    xAxis: { type: 'value', min: 0, name: 'Question attempts', minInterval: 1, axisLabel: { color: MUTED }, splitLine: { lineStyle: { color: GRID } } },
    yAxis: { type: 'value', min: 0, max: 100, name: 'Accuracy', axisLabel: { color: MUTED, formatter: '{value}%' }, splitLine: { lineStyle: { color: GRID } } },
    series: [{
      name: 'Topics practised',
      type: 'scatter',
      data: points.map((point) => [point.attempt_count, point.accuracy_percent, point.session_count, point.topic_name]),
      symbolSize: (value: unknown) => {
        const values = Array.isArray(value) ? value : [];
        return 14 + Math.sqrt(Number(values[2] ?? 0)) * 8;
      },
      itemStyle: { color: TEAL_LIGHT, opacity: 0.78, borderColor: TEAL, borderWidth: 1 },
    }],
  };
}

export function weakAreaOption(
  items: WeakAreaItem[],
  reducedMotion: boolean,
): EChartsCoreOption {
  return {
    ...baseOption(reducedMotion),
    color: [CORAL],
    grid: { left: 120, right: 30, top: 18, bottom: 34 },
    tooltip: { trigger: 'axis', renderMode: 'richText' },
    xAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: MUTED, formatter: '{value}%' }, splitLine: { lineStyle: { color: GRID } } },
    yAxis: { type: 'category', data: items.map((item) => item.display_name), axisLabel: { color: MUTED, width: 105, overflow: 'truncate' } },
    series: [{ name: 'Mastery', type: 'bar', data: items.map((item) => item.mastery_score), barMaxWidth: 28, itemStyle: { borderRadius: [0, 5, 5, 0] } }],
  };
}

export function illustrativeWeakAreaOption(reducedMotion: boolean): EChartsCoreOption {
  return {
    ...baseOption(reducedMotion),
    color: ['#b9c5c2'],
    grid: { left: 90, right: 20, top: 12, bottom: 26 },
    tooltip: { show: false },
    xAxis: { type: 'value', min: 0, max: 100, axisLabel: { show: false }, splitLine: { lineStyle: { color: GRID } } },
    yAxis: { type: 'category', data: ['Example A', 'Example B', 'Example C'], axisLabel: { color: MUTED } },
    series: [{ name: 'Example only', type: 'bar', silent: true, data: [34, 48, 57], barMaxWidth: 22, itemStyle: { borderRadius: [0, 5, 5, 0] } }],
  };
}
