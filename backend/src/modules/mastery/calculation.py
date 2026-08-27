from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP


HUNDREDTH = Decimal("0.01")
MIN_SCORE = Decimal("0.00")
MAX_SCORE = Decimal("100.00")
INITIAL_SCORE = Decimal("50.00")

_CORRECT_BASES = {
    1: Decimal("4"),
    2: Decimal("6"),
    3: Decimal("8"),
}
_INCORRECT_BASES = {
    1: Decimal("-8"),
    2: Decimal("-6"),
    3: Decimal("-4"),
}


def _clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def quantize_hundredth(value: Decimal) -> Decimal:
    return value.quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


def calculate_mastery_delta(
    is_correct: bool,
    difficulty: int,
    expected_time_seconds: int,
    actual_time_seconds: int,
) -> Decimal:
    if difficulty not in {1, 2, 3}:
        raise ValueError("difficulty must be between 1 and 3")
    if expected_time_seconds <= 0:
        raise ValueError("expected_time_seconds must be positive")
    if not 0 <= actual_time_seconds <= 3600:
        raise ValueError("actual_time_seconds must be between 0 and 3600")

    ratio = Decimal(actual_time_seconds) / Decimal(expected_time_seconds)
    raw_multiplier = Decimal("1.5") - Decimal("0.5") * ratio
    if is_correct:
        base = _CORRECT_BASES[difficulty]
        multiplier = _clamp(raw_multiplier, Decimal("0.50"), Decimal("1.25"))
    else:
        base = _INCORRECT_BASES[difficulty]
        multiplier = _clamp(raw_multiplier, Decimal("0.75"), Decimal("1.25"))
    return quantize_hundredth(base * multiplier)


def apply_mastery_delta(current_score: Decimal, delta: Decimal) -> Decimal:
    return quantize_hundredth(
        _clamp(Decimal(current_score) + Decimal(delta), MIN_SCORE, MAX_SCORE)
    )


def review_interval_days(final_score: Decimal, any_incorrect: bool) -> int:
    if any_incorrect or final_score < Decimal("40.00"):
        return 1
    if final_score < Decimal("60.00"):
        return 3
    if final_score < Decimal("80.00"):
        return 7
    return 14


def next_review_at(
    submitted_at: datetime,
    final_score: Decimal,
    any_incorrect: bool,
) -> datetime:
    return submitted_at + timedelta(
        days=review_interval_days(final_score, any_incorrect)
    )


@dataclass(frozen=True, slots=True)
class MasteryContribution:
    delta: Decimal
    is_correct: bool


@dataclass(frozen=True, slots=True)
class MasteryBatch:
    delta: Decimal
    attempt_count: int
    correct_count: int
    any_incorrect: bool


def aggregate_contributions(
    contributions: list[MasteryContribution],
) -> MasteryBatch:
    if not contributions:
        raise ValueError("at least one contribution is required")
    return MasteryBatch(
        delta=sum((entry.delta for entry in contributions), Decimal("0.00")),
        attempt_count=len(contributions),
        correct_count=sum(entry.is_correct for entry in contributions),
        any_incorrect=any(not entry.is_correct for entry in contributions),
    )
