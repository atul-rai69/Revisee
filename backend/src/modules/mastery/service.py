from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from src.modules.mastery.calculation import (
    MasteryBatch,
    apply_mastery_delta,
    next_review_at,
)
from src.modules.mastery import repository
from src.modules.mastery.schemas import (
    MasteryAnalyticsItemResponse,
    MasteryAnalyticsResponse,
    MasteryTrendPointResponse,
    RevisionActivityPointResponse,
    RevisionAnalyticsResponse,
    TopicPracticePointResponse,
)
from src.modules.mastery.weak_areas import MINIMUM_ATTEMPTS, accuracy_percent


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


class MasteryAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        user_id: int,
        *,
        entity_type: str,
        limit: int,
        offset: int,
    ) -> MasteryAnalyticsResponse:
        rows, total = repository.list_owned_mastery_analytics(
            self.db,
            user_id=user_id,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
        history = repository.list_mastery_history(
            self.db,
            user_id=user_id,
            entity_type=entity_type,
            entity_ids=[row.entity_id for row in rows],
        )
        items: list[MasteryAnalyticsItemResponse] = []
        for row in rows:
            if row.question_count == 0:
                evidence = "NO_QUESTIONS"
            elif row.total_attempts == 0:
                evidence = "NOT_ATTEMPTED"
            elif row.total_attempts < MINIMUM_ATTEMPTS:
                evidence = "INSUFFICIENT_EVIDENCE"
            else:
                evidence = "MEASURED"
            items.append(
                MasteryAnalyticsItemResponse(
                    entity_id=row.entity_id,
                    display_name=row.display_name,
                    question_count=row.question_count,
                    evidence_status=evidence,
                    mastery_score=(row.mastery_score if evidence == "MEASURED" else None),
                    total_attempts=row.total_attempts,
                    correct_attempts=row.correct_attempts,
                    accuracy_percent=accuracy_percent(row.correct_attempts, row.total_attempts),
                    last_practised_at=row.last_attempted_at,
                    next_review_at=(row.next_review_at if row.total_attempts > 0 else None),
                    trend=[
                        MasteryTrendPointResponse(
                            session_id=point.session_id,
                            recorded_at=point.recorded_at,
                            score_before=Decimal(point.score_before),
                            score_after=Decimal(point.score_after),
                            total_attempts=point.total_attempts,
                            correct_attempts=point.correct_attempts,
                        )
                        for point in history.get(row.entity_id, [])
                    ],
                )
            )
        self.db.rollback()
        return MasteryAnalyticsResponse(
            entity_type=entity_type,
            minimum_attempts=MINIMUM_ATTEMPTS,
            offset=offset,
            limit=limit,
            total=total,
            items=items,
        )


class RevisionAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int, session_limit: int) -> RevisionAnalyticsResponse:
        activity_rows, completed_count = repository.list_owned_revision_activity(
            self.db,
            user_id=user_id,
        )
        topic_rows, sessions_used = repository.list_owned_topic_practice(
            self.db,
            user_id=user_id,
            session_limit=session_limit,
        )
        measured_count = repository.count_owned_measured_learning_items(
            self.db,
            user_id=user_id,
        )
        self.db.rollback()
        return RevisionAnalyticsResponse(
            completed_session_count=completed_count,
            activity=[
                RevisionActivityPointResponse(
                    date=row.activity_date,
                    completed_session_count=row.completed_session_count,
                    answered_count=row.answered_count,
                    correct_count=row.correct_count,
                    accuracy_percent=accuracy_percent(
                        row.correct_count,
                        row.answered_count,
                    ),
                )
                for row in activity_rows
            ],
            requested_session_limit=session_limit,
            sessions_used=sessions_used,
            measured_learning_item_count=measured_count,
            weak_area_ready=measured_count > 0,
            minimum_attempts=MINIMUM_ATTEMPTS,
            topic_attribution="CURRENT_LEARNING_ITEM_TOPICS",
            attribution_note=(
                "Each persisted answer is attributed to every current Topic on its "
                "learning item, so Topic totals can overlap. Full Topic membership was "
                "not snapshotted for historical random and SMART sessions; later Topic "
                "changes can therefore affect this distribution."
            ),
            topic_practice=[
                TopicPracticePointResponse(
                    topic_id=row.topic_id,
                    topic_name=row.topic_name,
                    attempt_count=row.attempt_count,
                    correct_count=row.correct_count,
                    accuracy_percent=accuracy_percent(
                        row.correct_count,
                        row.attempt_count,
                    ),
                    session_count=row.session_count,
                )
                for row in topic_rows
            ],
        )
