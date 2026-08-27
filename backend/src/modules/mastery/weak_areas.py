from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


MINIMUM_ATTEMPTS = 3
WEAK_MASTERY_BELOW = Decimal("60.00")
HUNDREDTH = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class WeakAreaEvidence:
    classification: str | None
    evidence_status: str
    reason_code: str | None
    reason: str | None
    is_due: bool


def classify_weak_area(
    *,
    has_mastery_record: bool,
    mastery_score: Decimal | None,
    total_attempts: int,
    next_review_at: datetime | None,
    as_of: datetime,
) -> WeakAreaEvidence:
    is_due = next_review_at is not None and next_review_at <= as_of
    if not has_mastery_record:
        return WeakAreaEvidence(
            "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT",
            "NO_MASTERY_RECORD",
            "No mastery evidence has been recorded yet.",
            False,
        )
    if total_attempts < MINIMUM_ATTEMPTS:
        return WeakAreaEvidence(
            "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT",
            "BELOW_MINIMUM_ATTEMPTS",
            f"Fewer than {MINIMUM_ATTEMPTS} attempts are available.",
            is_due,
        )
    if mastery_score is not None and mastery_score < WEAK_MASTERY_BELOW:
        return WeakAreaEvidence(
            "DEMONSTRATED_WEAKNESS",
            "SUFFICIENT",
            "MASTERY_BELOW_THRESHOLD",
            f"Mastery is below {WEAK_MASTERY_BELOW} after sufficient attempts.",
            is_due,
        )
    if is_due:
        return WeakAreaEvidence(
            "DUE_REVIEW",
            "SUFFICIENT",
            "REVIEW_DUE",
            "The scheduled review is due.",
            True,
        )
    return WeakAreaEvidence(None, "SUFFICIENT", None, None, False)


def accuracy_percent(correct_attempts: int, total_attempts: int) -> Decimal | None:
    if total_attempts == 0:
        return None
    return (
        Decimal(correct_attempts) * Decimal("100") / Decimal(total_attempts)
    ).quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


def weak_area_order_key(
    *,
    classification: str,
    entity_id: int,
    mastery_score: Decimal | None,
    total_attempts: int,
    last_attempted_at: datetime | None,
    next_review_at: datetime | None,
    as_of: datetime,
) -> tuple[object, ...]:
    if classification == "DEMONSTRATED_WEAKNESS":
        return (
            Decimal(mastery_score),
            0 if next_review_at is not None and next_review_at <= as_of else 1,
            _datetime_key(next_review_at, nulls_first=False),
            -total_attempts,
            entity_id,
        )
    if classification == "DUE_REVIEW":
        return (
            _datetime_key(next_review_at, nulls_first=False),
            Decimal(mastery_score),
            -total_attempts,
            entity_id,
        )
    if classification == "INSUFFICIENT_EVIDENCE":
        return (
            -total_attempts,
            _datetime_key(last_attempted_at, nulls_first=True),
            entity_id,
        )
    raise ValueError("Unsupported weak-area classification")


def _datetime_key(value: datetime | None, *, nulls_first: bool) -> tuple[int, str]:
    if value is None:
        return (0 if nulls_first else 1, "")
    return (1 if nulls_first else 0, value.isoformat())
