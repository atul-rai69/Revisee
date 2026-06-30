from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
class UserLogin(BaseModel):
    username: str
    password: str

class CreateLabel(BaseModel):
    
    label_name: str


class UpdateLabel(BaseModel):
    id: int
    label_name: str

class deleteLearningItem(BaseModel):
    id: int

class DashboardSummaryResponse(BaseModel):
    username: str
    total_items: int
    total_labels: int
    login_streak: int


class LearningItemSummary(BaseModel):

    id: int
    title: str
    description_text: Optional[str]
    labels: Optional[str]
    image_urls: Optional[str]
    first_image_url: Optional[str]

    image_count: int
    pdf_count: int

    hours_ago: int


class LearningItemView(BaseModel):
    id: int
    title: str
    description_text: Optional[str]
    labels: Optional[str]
    image_urls: Optional[str]
    pdf_urls: Optional[str]
    first_image_url: Optional[str]
    image_count: int
    pdf_count: int
    hours_ago: int
    theory:  Optional[str] = None
    created_at: datetime
    updated_at: datetime
    


class LearningItemsSummaryResponse(BaseModel):

    message: str
    data: List[LearningItemSummary]


class LearningItemViewResponse(BaseModel):
    message: str
    data: LearningItemView


class GenerateRevisionRequest(BaseModel):
    title: str
    description: str


class MCQ(BaseModel):
    question: str
    options: list[str]
    description: str
    correct_answer: str


class GenerateRevisionResponse(BaseModel):
    theory: str
    questions: list[MCQ]