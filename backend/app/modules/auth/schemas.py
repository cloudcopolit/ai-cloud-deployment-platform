import uuid

from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_user_id: str
    name: str | None
    email: str | None
    avatar_url: str | None


class DevLoginRequest(BaseModel):
    github_user_id: str