from datetime import datetime
from decimal import Decimal

import pytest

from src.modules.mastery.calculation import (
    MasteryContribution,
    aggregate_contributions,
    apply_mastery_delta,
    calculate_mastery_delta,
    next_review_at,
    quantize_hundredth,
    review_interval_days,
)
from src.modules.mastery.service import apply_mastery_batches


@pytest.mark.parametrize(
    ("correct", "difficulty", "actual", "expected"),
    [
        (True, 1, 15, Decimal("5.00")),
        (True, 1, 60, Decimal("2.00")),
        (True, 3, 15, Decimal("10.00")),
        (True, 3, 60, Decimal("4.00")),
        (False, 1, 15, Decimal("-10.00")),
        (False, 1, 60, Decimal("-6.00")),
        (False, 3, 15, Decimal("-5.00")),
        (False, 3, 60, Decimal("-3.00")),
    ],
)
def test_mastery_scenario_matrix(
    correct: bool,
    difficulty: int,
    actual: int,
    expected: Decimal,
) -> None:
    assert calculate_mastery_delta(correct, difficulty, 30, actual) == expected


def test_time_multipliers_are_capped() -> None:
    assert calculate_mastery_delta(True, 3, 30, 0) == Decimal("10.00")
    assert calculate_mastery_delta(True, 3, 30, 3600) == Decimal("4.00")
    assert calculate_mastery_delta(False, 1, 30, 0) == Decimal("-10.00")
    assert calculate_mastery_delta(False, 1, 30, 3600) == Decimal("-6.00")


def test_scores_clamp_and_round_half_up() -> None:
    assert apply_mastery_delta(Decimal("98.00"), Decimal("5.00")) == Decimal("100.00")
    assert apply_mastery_delta(Decimal("2.00"), Decimal("-5.00")) == Decimal("0.00")
    assert quantize_hundredth(Decimal("1.005")) == Decimal("1.01")


@pytest.mark.parametrize(
    ("score", "incorrect", "days"),
    [
        (Decimal("99.00"), True, 1),
        (Decimal("39.99"), False, 1),
        (Decimal("40.00"), False, 3),
        (Decimal("60.00"), False, 7),
        (Decimal("80.00"), False, 14),
    ],
)
def test_review_schedule_boundaries(
    score: Decimal,
    incorrect: bool,
    days: int,
) -> None:
    assert review_interval_days(score, incorrect) == days
    started = datetime(2026, 8, 26, 10, 0, 0)
    assert (next_review_at(started, score, incorrect) - started).days == days


def test_aggregation_is_order_independent() -> None:
    first = [
        MasteryContribution(Decimal("4.25"), True),
        MasteryContribution(Decimal("-6.00"), False),
    ]
    assert aggregate_contributions(first) == aggregate_contributions(list(reversed(first)))
    batch = aggregate_contributions(first)
    assert batch.delta == Decimal("-1.75")
    assert batch.attempt_count == 2
    assert batch.correct_count == 1
    assert batch.any_incorrect is True


def test_apply_mastery_batch_updates_score_counters_and_schedule() -> None:
    submitted_at = datetime(2026, 8, 26, 10, 0, 0)
    record = type(
        "Record",
        (),
        {
            "mastery_score": Decimal("50.00"),
            "total_attempts": 2,
            "correct_attempts": 1,
            "last_attempt_at": None,
            "last_reviewed_at": None,
            "next_review_at": None,
        },
    )()
    batch = aggregate_contributions(
        [
            MasteryContribution(Decimal("7.50"), True),
            MasteryContribution(Decimal("-6.00"), False),
        ]
    )

    apply_mastery_batches({8: record}, {8: batch}, submitted_at)

    assert record.mastery_score == Decimal("51.50")
    assert record.total_attempts == 4
    assert record.correct_attempts == 2
    assert record.last_attempt_at == submitted_at
    assert record.last_reviewed_at == submitted_at
    assert record.next_review_at == datetime(2026, 8, 27, 10, 0, 0)
