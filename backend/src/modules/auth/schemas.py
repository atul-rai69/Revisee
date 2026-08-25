from pydantic import BaseModel, ConfigDict


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegistrationResponse(TokenResponse):
    message: str


class MessageResponse(BaseModel):
    message: str


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
