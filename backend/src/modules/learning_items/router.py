import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_ai_provider,
    get_current_user,
    get_storage_provider,
)
from src.core.exceptions import DomainValidationError
from src.db.session import get_db
from src.integrations.ai.base import AIProvider
from src.integrations.storage.base import StorageProvider
from src.modules.auth.models import User
from src.modules.learning_items.schemas import (
    DeleteLearningItem,
    LearningItemCreatedResponse,
    LearningItemViewResponse,
)
from src.modules.learning_items.service import LearningItemService


router = APIRouter(tags=["learning-items"])


@router.post("/learning-items", response_model=LearningItemCreatedResponse)
def create_learning_item(
    title: str = Form(...),
    description_text: str = Form(...),
    labels: str = Form(...),
    images: list[UploadFile] = File([]),
    pdfs: list[UploadFile] = File([]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    storage: StorageProvider = Depends(get_storage_provider),
) -> dict[str, str]:
    try:
        label_ids = json.loads(labels)
        if not isinstance(label_ids, list) or not all(
            isinstance(label_id, int) for label_id in label_ids
        ):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise DomainValidationError("labels must be a JSON array of integers") from exc

    return LearningItemService(db, ai_provider, storage).create(
        current_user.id,
        title,
        description_text,
        label_ids,
        images,
        pdfs,
    )


@router.delete("/learning-items", response_model=None)
def delete_learning_item(
    data: DeleteLearningItem,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage_provider),
) -> None:
    LearningItemService(db, None, storage).delete(current_user.id, data.id)


@router.get("/learning-item/{item_id}", response_model=LearningItemViewResponse)
def get_learning_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LearningItemService(db, None, None).get_detail(
        current_user.id,
        item_id,
    )
