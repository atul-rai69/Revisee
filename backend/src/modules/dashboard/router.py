from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.db.session import get_db
from src.modules.auth.models import User
from src.modules.dashboard.schemas import DashboardSummaryResponse
from src.modules.dashboard.service import DashboardService
from src.modules.learning_items.schemas import LearningItemsSummaryResponse


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return DashboardService(db).summary(current_user)


@router.get(
    "/dashboard/learning-items-summary",
    response_model=LearningItemsSummaryResponse,
)
def get_learning_items_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return DashboardService(db).learning_item_summaries(current_user.id)
