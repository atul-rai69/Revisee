from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from src.modules.mastery.calculation import (
    MasteryBatch,
    apply_mastery_delta,
    next_review_at,
)


class MasteryRecord(Protocol):
    mastery_score: Decimal
    total_attempts: int
    correct_attempts: int
    last_attempt_at: datetime | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None


def apply_mastery_batches(
    records: Mapping[int, MasteryRecord],
    batches: Mapping[int, MasteryBatch],
    submitted_at: datetime,
) -> None:
    if set(records) != set(batches):
        raise RuntimeError("mastery records changed during submission")

    for entity_id in sorted(batches):
        record = records[entity_id]
        batch = batches[entity_id]
        final_score = apply_mastery_delta(
            Decimal(record.mastery_score),
            batch.delta,
        )
        record.mastery_score = final_score
        record.total_attempts += batch.attempt_count
        record.correct_attempts += batch.correct_count
        record.last_attempt_at = submitted_at
        record.last_reviewed_at = submitted_at
        record.next_review_at = next_review_at(
            submitted_at,
            final_score,
            batch.any_incorrect,
        )
