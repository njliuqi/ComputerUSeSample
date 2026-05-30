from datetime import datetime

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    id: str
    username: str
    email: str | None
    created_at: datetime


class AuthRead(BaseModel):
    token: str
    user: UserRead
