from pydantic import BaseModel, ConfigDict


class CreateLabel(BaseModel):
    label_name: str


class UpdateLabel(BaseModel):
    id: int
    label_name: str


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    label_name: str


class LabelMutationResponse(BaseModel):
    message: str
    label: LabelResponse
