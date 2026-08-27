from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.modules.auth.models import User
from src.modules.mastery.schemas import (
    WeakAreaClassification,
    WeakAreaEntityType,
    WeakAreaQuery,
    WeakAreasResponse,
)
from src.modules.mastery.weak_area_service import WeakAreaService


router = APIRouter(tags=["mastery"])


@router.get("/weak-areas", response_model=WeakAreasResponse)
def get_weak_areas(
    entity_type: Annotated[WeakAreaEntityType, Query()] = "LEARNING_ITEM",
    classification: Annotated[
        WeakAreaClassification, Query()
    ] = "DEMONSTRATED_WEAKNESS",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeakAreasResponse:
    request = WeakAreaQuery(
        entity_type=entity_type,
        classification=classification,
        limit=limit,
        offset=offset,
    )
    return WeakAreaService(db).list(current_user.id, request)
