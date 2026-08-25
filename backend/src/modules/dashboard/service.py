from sqlalchemy.orm import Session

from src.modules.auth.models import User
from src.modules.dashboard import repository


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, user: User) -> dict[str, object]:
        sessions = repository.list_login_sessions(self.db, user.id)
        unique_days = {
            session.created_at.date()
            for session in sessions
            if session.created_at is not None
        }
        result = {
            "username": user.username,
            "total_items": repository.count_learning_items(self.db, user.id),
            "total_labels": repository.count_labels(self.db, user.id),
            "login_streak": len(unique_days),
        }
        self.db.rollback()
        return result

    def learning_item_summaries(self, user_id: int) -> dict[str, object]:
        rows = repository.list_learning_item_summaries(self.db, user_id)
        data = [
            {
                "id": row.id,
                "title": row.title,
                "description_text": row.description_text,
                "labels": row.labels,
                "image_urls": row.image_urls,
                "first_image_url": row.first_image_url,
                "image_count": row.image_count,
                "pdf_count": row.pdf_count,
                "hours_ago": int(row.hours_ago or 0),
            }
            for row in rows
        ]
        self.db.rollback()
        return {
            "message": "Learning items summary returned successfully",
            "data": data,
        }
