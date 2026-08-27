from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modules.mastery import repository
from src.modules.mastery.schemas import (
    WeakAreaCriteriaResponse,
    WeakAreaItemResponse,
    WeakAreaPaginationResponse,
    WeakAreaQuery,
    WeakAreasResponse,
)
from src.modules.mastery.weak_areas import (
    MINIMUM_ATTEMPTS,
    WEAK_MASTERY_BELOW,
    accuracy_percent,
    classify_weak_area,
)


class WeakAreaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, user_id: int, request: WeakAreaQuery) -> WeakAreasResponse:
        captured_as_of = datetime.now(timezone.utc)
        database_as_of = captured_as_of.replace(tzinfo=None)
        rows, total = repository.list_owned_weak_areas(
            self.db,
            user_id=user_id,
            entity_type=request.entity_type,
            classification=request.classification,
            as_of=database_as_of,
            limit=request.limit,
            offset=request.offset,
        )
        items: list[WeakAreaItemResponse] = []
        for row in rows:
            evidence = classify_weak_area(
                has_mastery_record=row.has_mastery_record,
                mastery_score=row.mastery_score,
                total_attempts=row.total_attempts,
                next_review_at=row.next_review_at,
                as_of=database_as_of,
            )
            if evidence.classification != request.classification:
                raise RuntimeError("weak-area query classification drifted from mapping")
            items.append(
                WeakAreaItemResponse(
                    entity_id=row.entity_id,
                    display_name=row.display_name,
                    has_mastery_record=row.has_mastery_record,
                    mastery_score=(
                        Decimal(row.mastery_score)
                        if row.mastery_score is not None
                        else None
                    ),
                    total_attempts=row.total_attempts,
                    correct_attempts=row.correct_attempts,
                    accuracy_percent=accuracy_percent(
                        row.correct_attempts,
                        row.total_attempts,
                    ),
                    evidence_status=evidence.evidence_status,
                    classification=request.classification,
                    reason_code=evidence.reason_code,
                    reason=evidence.reason,
                    last_attempted_at=row.last_attempted_at,
                    last_reviewed_at=row.last_reviewed_at,
                    next_review_at=row.next_review_at,
                    is_due=evidence.is_due,
                )
            )
        return WeakAreasResponse(
            entity_type=request.entity_type,
            classification=request.classification,
            as_of=captured_as_of,
            criteria=WeakAreaCriteriaResponse(
                minimum_attempts=MINIMUM_ATTEMPTS,
                weak_mastery_below=WEAK_MASTERY_BELOW,
            ),
            pagination=WeakAreaPaginationResponse(
                offset=request.offset,
                limit=request.limit,
                total=total,
            ),
            items=items,
        )
