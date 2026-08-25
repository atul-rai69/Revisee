from sqlalchemy.orm import Session

from src.core.exceptions import ResourceNotFoundError
from src.modules.labels import repository
from src.modules.labels.models import Label


class LabelService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_labels(self, user_id: int) -> list[Label]:
        return repository.list_for_user(self.db, user_id)

    def create_label(self, user_id: int, label_name: str) -> dict[str, object]:
        label = Label(user_id=user_id, label_name=label_name)
        repository.add(self.db, label)
        try:
            self.db.commit()
            self.db.refresh(label)
        except Exception:
            self.db.rollback()
            raise
        return {"message": "Label created", "label": label}

    def update_label(
        self,
        user_id: int,
        label_id: int,
        label_name: str,
    ) -> dict[str, object]:
        label = repository.find_owned(self.db, label_id, user_id)
        if not label:
            self.db.rollback()
            raise ResourceNotFoundError("Label not found")
        label.label_name = label_name
        try:
            self.db.commit()
            self.db.refresh(label)
        except Exception:
            self.db.rollback()
            raise
        return {"message": "Label updated", "label": label}
