from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.modules.auth.models import User
from src.modules.labels.schemas import (
    CreateLabel,
    LabelMutationResponse,
    LabelResponse,
    UpdateLabel,
)
from src.modules.labels.service import LabelService


router = APIRouter(tags=["labels"])


@router.get("/labels", response_model=list[LabelResponse])
def get_labels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[object]:
    return LabelService(db).list_labels(current_user.id)


@router.post("/labels", response_model=LabelMutationResponse)
def create_label(
    data: CreateLabel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LabelService(db).create_label(current_user.id, data.label_name)


@router.patch("/labels", response_model=LabelMutationResponse)
def update_label(
    data: UpdateLabel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LabelService(db).update_label(
        current_user.id,
        data.id,
        data.label_name,
    )
