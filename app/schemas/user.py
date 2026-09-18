from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRequest(BaseModel):
    email: EmailStr
    # bcrypt (core/security.py) rejects inputs over 72 bytes with a
    # ValueError, so cap it here to turn that into a clean 422 instead.
    password: str = Field(min_length=8, max_length=72)
    name: str


class UserUpdateRequest(BaseModel):
    # No password field here on purpose — see ARCH.md Decisions #10.
    email: EmailStr | None = None
    name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
