import { MasteryAnalyticsItem } from '../../core/services/mastery.service';
import {
  illustrativeWeakAreaOption,
  masteryGrowthOption,
} from './revisee-chart-options';

function item(
  id: number,
  name: string,
  sessionId: number,
  recordedAt: string,
): MasteryAnalyticsItem {
  return {
    entity_id: id,
    display_name: name,
    question_count: 3,
    evidence_status: 'MEASURED',
    mastery_score: 64,
    total_attempts: 3,
    correct_attempts: 2,
    accuracy_percent: 66.67,
    last_practised_at: recordedAt,
    next_review_at: null,
    trend: [{
      session_id: sessionId,
      recorded_at: recordedAt,
      score_before: 56,
      score_after: 64,
      total_attempts: 3,
      correct_attempts: 2,
    }],
  };
}

describe('Revisee chart options', () => {
  it('keeps one real mastery snapshot as one point', () => {
    const option = masteryGrowthOption([
      item(1, 'Databases', 10, '2026-09-10T10:00:00Z'),
    ], 3, true) as unknown as { series: Array<{ data: unknown[] }> };
    expect(option.series[0].data).toHaveLength(1);
    expect(option.series[0].data[0]).not.toBeNull();
  });

  it('uses null gaps rather than connecting missing Topic observations', () => {
    const option = masteryGrowthOption([
      item(1, 'Databases', 10, '2026-09-10T10:00:00Z'),
      item(2, 'Networks', 11, '2026-09-11T10:00:00Z'),
    ], 3, true) as unknown as { series: Array<{ connectNulls: boolean; data: unknown[] }> };
    expect(option.series[0].connectNulls).toBe(false);
    expect(option.series[0].data).toContain(null);
    expect(option.series[1].data).toContain(null);
  });

  it('makes the illustrative weak-area preview silent and non-personalised', () => {
    const option = illustrativeWeakAreaOption(true) as unknown as {
      tooltip: { show: boolean };
      series: Array<{ name: string; silent: boolean }>;
    };
    expect(option.tooltip.show).toBe(false);
    expect(option.series[0]).toMatchObject({ name: 'Example only', silent: true });
  });
});
