from datetime import datetime, timedelta
from decimal import Decimal

from src.modules.mastery.weak_areas import (
    accuracy_percent,
    classify_weak_area,
    weak_area_order_key,
)
from src.modules.mastery.repository import WeakAreaRow
from src.modules.mastery.schemas import WeakAreaQuery
from src.modules.mastery.weak_area_service import WeakAreaService


AS_OF = datetime(2026, 8, 27, 12, 0, 0)


def classify(
    *,
    has_record: bool = True,
    score: str | None = "50.00",
    attempts: int = 3,
    next_review_at: datetime | None = None,
):
    return classify_weak_area(
        has_mastery_record=has_record,
        mastery_score=Decimal(score) if score is not None else None,
        total_attempts=attempts,
        next_review_at=next_review_at,
        as_of=AS_OF,
    )


def test_missing_mastery_and_initial_zero_attempt_score_are_insufficient() -> None:
    missing = classify(has_record=False, score=None, attempts=0)
    initial = classify(score="50.00", attempts=0)

    assert missing.classification == "INSUFFICIENT_EVIDENCE"
    assert missing.reason_code == "NO_MASTERY_RECORD"
    assert initial.classification == "INSUFFICIENT_EVIDENCE"
    assert initial.reason_code == "BELOW_MINIMUM_ATTEMPTS"


def test_two_attempt_low_score_remains_insufficient() -> None:
    evidence = classify(score="10.00", attempts=2)
    assert evidence.classification == "INSUFFICIENT_EVIDENCE"


def test_exact_attempt_and_mastery_threshold_boundaries() -> None:
    assert classify(score="59.99", attempts=3).classification == (
        "DEMONSTRATED_WEAKNESS"
    )
    assert classify(score="60.00", attempts=3).classification is None
    assert classify(
        score="60.00", attempts=3, next_review_at=AS_OF
    ).classification == "DUE_REVIEW"


def test_weakness_precedes_due_review() -> None:
    evidence = classify(
        score="40.00",
        attempts=4,
        next_review_at=AS_OF - timedelta(days=2),
    )
    assert evidence.classification == "DEMONSTRATED_WEAKNESS"
    assert evidence.is_due is True


def test_strong_overdue_is_due_but_null_or_future_review_is_stable() -> None:
    assert classify(
        score="80.00", attempts=3, next_review_at=AS_OF - timedelta(seconds=1)
    ).classification == "DUE_REVIEW"
    assert classify(score="80.00", attempts=3).classification is None
    assert classify(
        score="80.00", attempts=3, next_review_at=AS_OF + timedelta(seconds=1)
    ).classification is None


def test_accuracy_uses_decimal_half_up_rounding() -> None:
    assert accuracy_percent(2, 3) == Decimal("66.67")
    assert accuracy_percent(0, 0) is None


def test_classification_ordering_is_stable_with_entity_id_tie_breaker() -> None:
    rows = [
        (2, Decimal("20.00"), 3, None),
        (1, Decimal("20.00"), 3, None),
        (3, Decimal("10.00"), 3, None),
    ]
    ordered = sorted(
        rows,
        key=lambda row: weak_area_order_key(
            classification="DEMONSTRATED_WEAKNESS",
            entity_id=row[0],
            mastery_score=row[1],
            total_attempts=row[2],
            last_attempted_at=None,
            next_review_at=row[3],
            as_of=AS_OF,
        ),
    )
    assert [row[0] for row in ordered] == [3, 1, 2]


def test_service_uses_one_as_of_and_preserves_missing_mastery_nulls(
    monkeypatch,
) -> None:
    from src.modules.mastery import repository

    captured: dict[str, object] = {}

    def fake_list(_db, **kwargs):
        captured.update(kwargs)
        return (
            [
                WeakAreaRow(
                    entity_id=7,
                    display_name="Unpractised",
                    has_mastery_record=False,
                    mastery_score=None,
                    total_attempts=0,
                    correct_attempts=0,
                    last_attempted_at=None,
                    last_reviewed_at=None,
                    next_review_at=None,
                )
            ],
            1,
        )

    monkeypatch.setattr(repository, "list_owned_weak_areas", fake_list)
    response = WeakAreaService(object()).list(  # type: ignore[arg-type]
        5,
        WeakAreaQuery(classification="INSUFFICIENT_EVIDENCE"),
    )

    assert response.as_of.replace(tzinfo=None) == captured["as_of"]
    assert response.pagination.total == 1
    item = response.items[0]
    assert item.mastery_score is None
    assert item.accuracy_percent is None
    assert item.reason_code == "NO_MASTERY_RECORD"
