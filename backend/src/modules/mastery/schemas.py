from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


WeakAreaEntityType = Literal["LEARNING_ITEM", "LABEL"]
WeakAreaClassification = Literal[
    "DEMONSTRATED_WEAKNESS",
    "DUE_REVIEW",
    "INSUFFICIENT_EVIDENCE",
]
WeakAreaReasonCode = Literal[
    "NO_MASTERY_RECORD",
    "BELOW_MINIMUM_ATTEMPTS",
    "MASTERY_BELOW_THRESHOLD",
    "REVIEW_DUE",
]


class WeakAreaCriteriaResponse(BaseModel):
    minimum_attempts: int
    weak_mastery_below: Decimal

    @field_serializer("weak_mastery_below")
    def serialize_weak_mastery_below(self, value: Decimal) -> float:
        return float(value)


class WeakAreaPaginationResponse(BaseModel):
    offset: int
    limit: int
    total: int


class WeakAreaItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: int
    display_name: str
    has_mastery_record: bool
    mastery_score: Decimal | None
    total_attempts: int
    correct_attempts: int
    accuracy_percent: Decimal | None
    evidence_status: Literal["SUFFICIENT", "INSUFFICIENT"]
    classification: WeakAreaClassification
    reason_code: WeakAreaReasonCode
    reason: str
    last_attempted_at: datetime | None
    last_reviewed_at: datetime | None
    next_review_at: datetime | None
    is_due: bool

    @field_serializer("mastery_score", "accuracy_percent")
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class WeakAreasResponse(BaseModel):
    entity_type: WeakAreaEntityType
    classification: WeakAreaClassification
    as_of: datetime
    criteria: WeakAreaCriteriaResponse
    pagination: WeakAreaPaginationResponse
    items: list[WeakAreaItemResponse]


class WeakAreaQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: WeakAreaEntityType = "LEARNING_ITEM"
    classification: WeakAreaClassification = "DEMONSTRATED_WEAKNESS"
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10000)
