import logging
import unicodedata
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.core.exceptions import DuplicateQuestionError, ResourceNotFoundError
from src.integrations.ai.base import AIProvider
from src.integrations.storage.base import StorageProvider, UploadedAsset
from src.modules.labels import repository as label_repository
from src.modules.learning_items import repository
from src.modules.learning_items.models import LearningItem, PdfNote
from src.modules.revisions import repository as revision_repository
from src.modules.revisions.service import RevisionService
from src.modules.revisions.models import Question
from src.modules.revisions.generation.fingerprint import question_fingerprint
from src.modules.learning_items.schemas import (
    ManualQuestionCreateRequest,
    PdfNoteCreateRequest,
    PdfNoteUpdateRequest,
)


logger = logging.getLogger(__name__)


class LearningItemService:
    def __init__(
        self,
        db: Session,
        ai_provider: AIProvider | None,
        storage: StorageProvider | None,
    ) -> None:
        self.db = db
        self.ai_provider = ai_provider
        self.storage = storage

    def create(
        self,
        user_id: int,
        title: str,
        description_text: str,
        label_ids: list[int],
        images: list[UploadFile],
        pdfs: list[UploadFile],
        *,
        personal_remarks: str | None = None,
        credential_id: int | None = None,
    ) -> dict[str, str]:
        if self.ai_provider is None or self.storage is None:
            raise RuntimeError("Learning-item creation providers are not configured")
        unique_label_ids = list(dict.fromkeys(label_ids))
        owned_ids = label_repository.owned_ids(self.db, unique_label_ids, user_id)
        if owned_ids != set(unique_label_ids):
            self.db.rollback()
            raise ResourceNotFoundError("Label not found")
        self.db.rollback()

        revision_service = RevisionService(self.db, self.ai_provider)
        if credential_id is None:
            generated = revision_service.generate_content(title, description_text)
        else:
            generated, _ = revision_service.generate_content_with_usage(
                title,
                description_text,
                personal_remarks,
            )

        uploaded: list[tuple[str, UploadedAsset, str | None]] = []
        try:
            for image in images:
                uploaded.append((
                    "image",
                    self.storage.upload(image.file, "image"),
                    self._safe_original_filename(image.filename),
                ))
            for pdf in pdfs:
                uploaded.append((
                    "pdf",
                    self.storage.upload(pdf.file, "raw"),
                    self._safe_original_filename(pdf.filename),
                ))
        except Exception:
            self._compensate(uploaded)
            raise

        learning_item = LearningItem(
            user_id=user_id,
            title=title,
            description_text=description_text,
            theory=None,
        )
        try:
            repository.add(self.db, learning_item)
            self.db.flush()
            repository.add_label_relations(self.db, learning_item.id, unique_label_ids)
            for media_type, asset, original_filename in uploaded:
                repository.add_media(
                    self.db,
                    learning_item.id,
                    media_type,
                    asset.url,
                    asset.public_id,
                    original_filename,
                )
            revision_repository.add_generated_content(self.db, learning_item, generated)
            self.db.commit()
        except Exception:
            self.db.rollback()
            self._compensate(uploaded)
            raise

        return {"message": "Learning item created"}

    def get_detail(self, user_id: int, item_id: int) -> dict[str, object]:
        learning_item = repository.find_owned(self.db, item_id, user_id)
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        labels = repository.list_label_names(self.db, item_id)
        media = repository.list_media(self.db, item_id)
        key_points = repository.list_key_points(self.db, item_id)
        questions = repository.list_questions(self.db, item_id)
        statistics = repository.list_question_statistics_for_user(
            self.db, user_id, [question.id for question in questions]
        )

        image_urls = [entry.url for entry in media if entry.type == "image"]
        pdf_urls = [entry.url for entry in media if entry.type == "pdf"]
        pdf_resources = [
            {
                "id": entry.id,
                "url": entry.url,
                "original_filename": entry.original_filename,
            }
            for entry in media
            if entry.type == "pdf"
        ]
        formatted_questions = [
            {
                "question_id": question.id,
                "number": index,
                "question": question.question_text,
                "options": [
                    {
                        "label": "A",
                        "text": question.option_a,
                        "isCorrect": question.correct_option == "0",
                    },
                    {
                        "label": "B",
                        "text": question.option_b,
                        "isCorrect": question.correct_option == "1",
                    },
                    {
                        "label": "C",
                        "text": question.option_c,
                        "isCorrect": question.correct_option == "2",
                    },
                    {
                        "label": "D",
                        "text": question.option_d,
                        "isCorrect": question.correct_option == "3",
                    },
                ],
                "explanation": question.explanation,
                "difficulty": question.difficulty,
                "expected_time_seconds": question.expected_time_seconds,
                "total_attempts": statistics.get(question.id, (0, 0))[0],
                "correct_attempts": statistics.get(question.id, (0, 0))[1],
                "accuracy_percent": (
                    round(
                        statistics[question.id][1] * 100 / statistics[question.id][0],
                        2,
                    )
                    if statistics.get(question.id, (0, 0))[0] > 0
                    else None
                ),
            }
            for index, question in enumerate(questions, start=1)
        ]

        data = {
            "id": learning_item.id,
            "title": learning_item.title,
            "description_text": learning_item.description_text,
            "labels": ", ".join(labels) if labels else None,
            "image_urls": ",".join(image_urls) if image_urls else None,
            "pdf_urls": ",".join(pdf_urls) if pdf_urls else None,
            "pdf_resources": pdf_resources,
            "first_image_url": image_urls[0] if image_urls else None,
            "image_count": len(image_urls),
            "pdf_count": len(pdf_urls),
            "hours_ago": self._hours_ago(learning_item.created_at),
            "theory": learning_item.theory,
            "key_points": key_points,
            "questions": formatted_questions,
            "created_at": learning_item.created_at,
            "updated_at": learning_item.updated_at,
        }
        self.db.rollback()
        return {"message": "Learning item data fetched successfully", "data": data}

    def list_pdf_notes(self, user_id: int, item_id: int) -> dict[str, object]:
        learning_item = repository.find_owned(self.db, item_id, user_id)
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")
        notes = repository.list_pdf_notes(self.db, user_id=user_id, item_id=item_id)
        response = {"notes": [self._pdf_note_response(note) for note in notes]}
        self.db.rollback()
        return response

    def create_pdf_note(
        self,
        user_id: int,
        item_id: int,
        request: PdfNoteCreateRequest,
    ) -> dict[str, object]:
        learning_item = repository.find_owned(self.db, item_id, user_id)
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")
        media = repository.find_owned_pdf_media(
            self.db,
            media_id=request.media_id,
            learning_item_id=item_id,
            user_id=user_id,
        )
        if not media:
            self.db.rollback()
            raise ResourceNotFoundError("PDF attachment not found")

        note = PdfNote(
            user_id=user_id,
            learning_item_id=item_id,
            media_id=media.id,
            page_number=request.page_number,
            source_excerpt=request.source_excerpt,
            note_text=request.note_text,
        )
        try:
            repository.add_pdf_note(self.db, note)
            self.db.flush()
            response = self._pdf_note_response(note)
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def update_pdf_note(
        self,
        user_id: int,
        item_id: int,
        note_id: int,
        request: PdfNoteUpdateRequest,
    ) -> dict[str, object]:
        note = repository.find_owned_pdf_note(
            self.db,
            note_id=note_id,
            item_id=item_id,
            user_id=user_id,
        )
        if not note:
            self.db.rollback()
            raise ResourceNotFoundError("PDF note not found")
        note.note_text = request.note_text
        note.source_excerpt = request.source_excerpt
        note.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            self.db.flush()
            response = self._pdf_note_response(note)
            self.db.commit()
            return response
        except Exception:
            self.db.rollback()
            raise

    def delete_pdf_note(
        self,
        user_id: int,
        item_id: int,
        note_id: int,
    ) -> None:
        note = repository.find_owned_pdf_note(
            self.db,
            note_id=note_id,
            item_id=item_id,
            user_id=user_id,
        )
        if not note:
            self.db.rollback()
            raise ResourceNotFoundError("PDF note not found")
        try:
            self.db.delete(note)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def create_question(
        self,
        user_id: int,
        item_id: int,
        request: ManualQuestionCreateRequest,
    ) -> dict[str, object]:
        learning_item = repository.find_owned(self.db, item_id, user_id)
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")
        options = (request.option_a, request.option_b, request.option_c, request.option_d)
        fingerprint = question_fingerprint(request.question, options)
        existing_questions = repository.list_questions(self.db, item_id)
        if any(
            (question.content_fingerprint or question_fingerprint(
                question.question_text,
                (question.option_a, question.option_b, question.option_c, question.option_d),
            )) == fingerprint
            for question in existing_questions
        ):
            self.db.rollback()
            raise DuplicateQuestionError()
        question = Question(
            learning_item_id=item_id,
            question_text=request.question,
            option_a=request.option_a,
            option_b=request.option_b,
            option_c=request.option_c,
            option_d=request.option_d,
            correct_option={"A": "0", "B": "1", "C": "2", "D": "3"}[request.correct_option],
            explanation=request.explanation,
            difficulty=request.difficulty,
            expected_time_seconds=request.expected_time_seconds,
            source="manual",
            content_fingerprint=fingerprint,
        )
        try:
            repository.add_question(self.db, question)
            self.db.flush()
            question_id = question.id
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            from sqlalchemy.exc import IntegrityError
            if isinstance(exc, IntegrityError):
                raise DuplicateQuestionError() from exc
            raise
        return {"message": "Question added", "question_id": question_id}

    def delete(self, user_id: int, item_id: int) -> None:
        if self.storage is None:
            raise RuntimeError("Media storage provider is not configured")
        learning_item = repository.find_owned(self.db, item_id, user_id)
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")
        media = repository.list_media(self.db, item_id)
        cleanup_targets = [
            (entry.public_id, "raw" if entry.type == "pdf" else "image")
            for entry in media
        ]
        try:
            repository.delete_owned(self.db, learning_item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        cleanup_failures = 0
        for public_id, resource_type in cleanup_targets:
            try:
                self.storage.delete(public_id, resource_type)
            except Exception:
                cleanup_failures += 1
        if cleanup_failures:
            logger.warning(
                "Cloudinary cleanup failed after learning-item deletion; count=%d",
                cleanup_failures,
            )

    def _compensate(
        self,
        uploaded: list[tuple[str, UploadedAsset, str | None]],
    ) -> None:
        if self.storage is None:
            return
        cleanup_failures = 0
        for _, asset, _ in reversed(uploaded):
            try:
                self.storage.delete(asset.public_id, asset.resource_type)
            except Exception:
                cleanup_failures += 1
        if cleanup_failures:
            logger.warning(
                "Cloudinary compensation was incomplete; count=%d",
                cleanup_failures,
            )

    @staticmethod
    def _safe_original_filename(value: str | None) -> str | None:
        if not value:
            return None
        # Browsers normally send a basename, but never persist a client path or
        # control characters if a non-browser client supplies them.
        candidate = value.replace("\\", "/").rsplit("/", 1)[-1]
        candidate = "".join(
            character
            for character in candidate
            if not unicodedata.category(character).startswith("C")
        ).strip()
        if not candidate or candidate in {".", ".."}:
            return None
        if len(candidate) <= 255:
            return candidate
        stem, separator, suffix = candidate.rpartition(".")
        if separator and stem and len(suffix) <= 20:
            return f"{stem[:254 - len(suffix)]}.{suffix}"
        return candidate[:255]

    @staticmethod
    def _hours_ago(created_at: datetime | None) -> int:
        if not created_at:
            return 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return max(0, int((now - created_at).total_seconds() // 3600))

    @staticmethod
    def _pdf_note_response(note: PdfNote) -> dict[str, object]:
        return {
            "id": note.id,
            "learning_item_id": note.learning_item_id,
            "media_id": note.media_id,
            "page_number": note.page_number,
            "source_excerpt": note.source_excerpt,
            "note_text": note.note_text,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
