from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
