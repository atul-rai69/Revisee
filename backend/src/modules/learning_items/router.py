import json

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_ai_provider,
    get_current_user,
    get_personal_ai_provider_factory,
    get_storage_provider,
)
from src.core.exceptions import DomainValidationError
from src.db.session import get_db
from src.integrations.ai.base import AIProvider
from src.integrations.ai.base import AIOperation
from src.integrations.storage.base import StorageProvider
from src.modules.auth.models import User
from src.modules.learning_items.schemas import (
    DeleteLearningItem,
    LearningItemCreatedResponse,
    LearningItemViewResponse,
    ManualQuestionCreateRequest,
    ManualQuestionCreatedResponse,
    PdfNoteCreateRequest,
    PdfNoteResponse,
    PdfNotesResponse,
    PdfNoteUpdateRequest,
)
from src.modules.learning_items.service import LearningItemService
from src.modules.ai_credentials.provider import PersonalAIProviderFactory
from src.modules.ai_credentials.service import AICredentialService
from src.modules.revisions.generation.service import QuestionGenerationService
from src.modules.revisions.schemas import GenerateQuestionsRequest, GeneratedQuestionsResponse
from src.core.config import Settings, get_settings


router = APIRouter(tags=["learning-items"])


def _upload_size(upload: UploadFile) -> int:
    if upload.size is not None:
        return upload.size
    position = upload.file.tell()
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(position)
    return size


def _validate_upload_sizes(
    uploads: list[UploadFile],
    *,
    maximum_bytes: int,
    media_label: str,
) -> None:
    if any(_upload_size(upload) > maximum_bytes for upload in uploads):
        maximum_megabytes = maximum_bytes / (1024 * 1024)
        display_limit = (
            str(int(maximum_megabytes))
            if maximum_megabytes.is_integer()
            else f"{maximum_megabytes:.1f}"
        )
        raise DomainValidationError(
            f"Each {media_label} must be {display_limit} MB or smaller"
        )


def _selected_provider(
    *,
    user_id: int,
    generation_source: Literal["REVISEE", "PERSONAL"],
    credential_id: int | None,
    db: Session,
    settings: Settings,
    default_provider: AIProvider,
    factory: PersonalAIProviderFactory,
) -> tuple[AIProvider, int | None]:
    if generation_source == "REVISEE":
        if credential_id is not None:
            raise DomainValidationError(
                "credential_id is only valid for personal generation"
            )
        return default_provider, None
    if credential_id is None:
        raise DomainValidationError(
            "credential_id is required for personal generation"
        )
    return (
        AICredentialService(db, settings, factory).resolve_provider(
            user_id, credential_id
        ),
        credential_id,
    )


@router.post(
    "/learning-items/{item_id}/questions",
    response_model=ManualQuestionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_question(
    item_id: int,
    request: ManualQuestionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LearningItemService(db, None, None).create_question(
        current_user.id, item_id, request
    )


@router.get(
    "/learning-items/{item_id}/pdf-notes",
    response_model=PdfNotesResponse,
)
def list_pdf_notes(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LearningItemService(db, None, None).list_pdf_notes(
        current_user.id, item_id
    )


@router.post(
    "/learning-items/{item_id}/pdf-notes",
    response_model=PdfNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pdf_note(
    item_id: int,
    request: PdfNoteCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LearningItemService(db, None, None).create_pdf_note(
        current_user.id, item_id, request
    )


@router.patch(
    "/learning-items/{item_id}/pdf-notes/{note_id}",
    response_model=PdfNoteResponse,
)
def update_pdf_note(
    item_id: int,
    note_id: int,
    request: PdfNoteUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return LearningItemService(db, None, None).update_pdf_note(
        current_user.id, item_id, note_id, request
    )


@router.delete(
    "/learning-items/{item_id}/pdf-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_pdf_note(
    item_id: int,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    LearningItemService(db, None, None).delete_pdf_note(
        current_user.id, item_id, note_id
    )


@router.post("/learning-items", response_model=LearningItemCreatedResponse)
def create_learning_item(
    title: str = Form(...),
    description_text: str = Form(...),
    labels: str = Form(...),
    images: list[UploadFile] = File([]),
    pdfs: list[UploadFile] = File([]),
    generation_source: Literal["REVISEE", "PERSONAL"] = Form("REVISEE"),
    credential_id: int | None = Form(None),
    personal_remarks: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    storage: StorageProvider = Depends(get_storage_provider),
    settings: Settings = Depends(get_settings),
    personal_provider_factory: PersonalAIProviderFactory = Depends(
        get_personal_ai_provider_factory
    ),
) -> dict[str, str]:
    _validate_upload_sizes(
        images,
        maximum_bytes=settings.CLOUDINARY_MAX_IMAGE_BYTES,
        media_label="image",
    )
    _validate_upload_sizes(
        pdfs,
        maximum_bytes=settings.CLOUDINARY_MAX_RAW_BYTES,
        media_label="PDF",
    )
    try:
        label_ids = json.loads(labels)
        if not isinstance(label_ids, list) or not all(
            isinstance(label_id, int) for label_id in label_ids
        ):
            raise ValueError
    except (json.JSONDecodeError, ValueError) as exc:
        raise DomainValidationError("labels must be a JSON array of integers") from exc

    title = title.strip()
    description_text = description_text.strip()
    personal_remarks = personal_remarks.strip() if personal_remarks else None
    if not 3 <= len(title) <= 100:
        raise DomainValidationError("title must contain 3 to 100 characters")
    if not description_text or len(description_text) > settings.AI_MAX_SOURCE_CHARACTERS:
        raise DomainValidationError("learning-item notes exceed the configured limit")
    if personal_remarks and len(personal_remarks) > settings.AI_MAX_PERSONAL_REMARKS_CHARACTERS:
        raise DomainValidationError("personal remarks exceed the configured limit")
    if generation_source == "REVISEE" and personal_remarks:
        raise DomainValidationError("personal remarks require a personal credential")
    selected_provider, selected_credential_id = _selected_provider(
        user_id=current_user.id,
        generation_source=generation_source,
        credential_id=credential_id,
        db=db,
        settings=settings,
        default_provider=ai_provider,
        factory=personal_provider_factory,
    )

    return LearningItemService(db, selected_provider, storage).create(
        current_user.id,
        title,
        description_text,
        label_ids,
        images,
        pdfs,
        personal_remarks=personal_remarks,
        credential_id=selected_credential_id,
    )


@router.post(
    "/learning-items/{item_id}/generated-questions",
    response_model=GeneratedQuestionsResponse,
)
def generate_learning_item_questions(
    item_id: int,
    request: GenerateQuestionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
    personal_provider_factory: PersonalAIProviderFactory = Depends(
        get_personal_ai_provider_factory
    ),
) -> GeneratedQuestionsResponse:
    if (
        request.personal_remarks
        and len(request.personal_remarks) > settings.AI_MAX_PERSONAL_REMARKS_CHARACTERS
    ):
        raise DomainValidationError("personal remarks exceed the configured limit")
    provider, credential_id = _selected_provider(
        user_id=current_user.id,
        generation_source=request.generation_source,
        credential_id=request.credential_id,
        db=db,
        settings=settings,
        default_provider=ai_provider,
        factory=personal_provider_factory,
    )
    result = QuestionGenerationService(db, provider, settings).generate_for_owned_item(
        user_id=current_user.id,
        learning_item_id=item_id,
        question_count=request.question_count,
        operation=AIOperation.LEARNING_ITEM_QUESTIONS,
        personal_remarks=request.personal_remarks,
        credential_id=credential_id,
    )
    return GeneratedQuestionsResponse(
        message="Questions generated and appended",
        status=result.status,
        requested_count=result.requested_count,
        saved_count=len(result.persisted_question_ids),
        duplicate_count=result.duplicate_count,
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
