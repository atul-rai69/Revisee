from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    username: str
    total_items: int
    total_labels: int
    login_streak: int
