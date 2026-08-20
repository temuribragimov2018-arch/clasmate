from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    invite_code: str = Field(..., min_length=4, max_length=20)
    email: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must contain only letters, numbers and underscores")
        return v.lower()


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    status: Optional[str] = None
    role: str
    is_online: bool
    last_activity: Optional[datetime] = None
    is_pro: bool
    pro_until: Optional[datetime] = None
    theme: str = "light"
    streak: int = 0
    coin_balance: int = 0
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    monetization_enabled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[str] = Field(None, max_length=150)
    theme: Optional[str] = None
    avatar_url: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class PasswordResetRequest(BaseModel):
    username: str
    email: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=100)
