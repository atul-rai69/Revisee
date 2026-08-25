import json

from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.exceptions import ProviderOutputError, ResourceNotFoundError
from src.integrations.ai.base import AIProvider
from src.modules.learning_items import repository as learning_item_repository
from src.modules.revisions import repository
from src.modules.revisions.prompt import build_revision_prompt
from src.modules.revisions.schemas import GeneratedRevisionResponse


class RevisionService:
    def __init__(self, db: Session, provider: AIProvider) -> None:
        self.db = db
        self.provider = provider

    def generate_content(self, title: str, description: str) -> GeneratedRevisionResponse:
        raw_content = self.provider.generate(build_revision_prompt(title, description))
        try:
            decoded = json.loads(raw_content)
            return GeneratedRevisionResponse.model_validate(decoded)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise ProviderOutputError("Revision provider returned invalid data") from exc

    def generate_for_owned_item(
        self,
        user_id: int,
        learning_item_id: int,
        title: str,
        description: str,
    ) -> dict[str, str]:
        learning_item = learning_item_repository.find_owned(
            self.db,
            learning_item_id,
            user_id,
        )
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        self.db.rollback()
        content = self.generate_content(title, description)

        learning_item = learning_item_repository.find_owned(
            self.db,
            learning_item_id,
            user_id,
        )
        if not learning_item:
            self.db.rollback()
            raise ResourceNotFoundError("Learning item not found")

        repository.add_generated_content(self.db, learning_item, content)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"message": "Revision content generated successfully."}
