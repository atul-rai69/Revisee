import logging
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.core.exceptions import ResourceNotFoundError
from src.integrations.ai.base import AIProvider
from src.integrations.storage.base import StorageProvider, UploadedAsset
from src.modules.labels import repository as label_repository
from src.modules.learning_items import repository
from src.modules.learning_items.models import LearningItem
from src.modules.revisions import repository as revision_repository
from src.modules.revisions.service import RevisionService


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
    ) -> dict[str, str]:
        if self.ai_provider is None or self.storage is None:
            raise RuntimeError("Learning-item creation providers are not configured")
        unique_label_ids = list(dict.fromkeys(label_ids))
        owned_ids = label_repository.owned_ids(self.db, unique_label_ids, user_id)
        if owned_ids != set(unique_label_ids):
            self.db.rollback()
            raise ResourceNotFoundError("Label not found")
        self.db.rollback()

        generated = RevisionService(self.db, self.ai_provider).generate_content(
            title,
            description_text,
        )

        uploaded: list[tuple[str, UploadedAsset]] = []
        try:
            for image in images:
                uploaded.append(("image", self.storage.upload(image.file, "image")))
            for pdf in pdfs:
                uploaded.append(("pdf", self.storage.upload(pdf.file, "raw")))
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
            for media_type, asset in uploaded:
                repository.add_media(
                    self.db,
                    learning_item.id,
                    media_type,
                    asset.url,
                    asset.public_id,
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

        image_urls = [entry.url for entry in media if entry.type == "image"]
        pdf_urls = [entry.url for entry in media if entry.type == "pdf"]
        formatted_questions = [
            {
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

    def _compensate(self, uploaded: list[tuple[str, UploadedAsset]]) -> None:
        if self.storage is None:
            return
        cleanup_failures = 0
        for _, asset in reversed(uploaded):
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
    def _hours_ago(created_at: datetime | None) -> int:
        if not created_at:
            return 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return max(0, int((now - created_at).total_seconds() // 3600))
