from datetime import datetime, time
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal


class HomeworkCreate(BaseModel):
    subject: str
    title: str
    description: Optional[str] = None
    due_date: datetime
    file_url: Optional[str] = None


class HomeworkOut(BaseModel):
    id: int
    subject: str
    title: str
    description: Optional[str]
    due_date: datetime
    file_url: Optional[str]
    created_at: datetime
    status: Optional[str] = "new"

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    lesson_number: int
    subject: str
    room: Optional[str] = None
    teacher: Optional[str] = None
    start_time: time
    end_time: time


class ScheduleOut(BaseModel):
    id: int
    day_of_week: int
    lesson_number: int
    subject: str
    room: Optional[str] = None
    teacher: Optional[str] = None
    start_time: str
    end_time: str

    class Config:
        from_attributes = True


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    image_url: Optional[str] = None
    is_pinned: bool = False
    is_important: bool = False


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    image_url: Optional[str]
    is_pinned: bool
    is_important: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PollCreate(BaseModel):
    question: str
    options: List[str] = Field(..., min_length=2)
    ends_at: Optional[datetime] = None


class PollOut(BaseModel):
    id: int
    question: str
    ends_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    options: List[dict] = []
    user_voted: bool = False

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str = "other"
    start_at: datetime
    end_at: Optional[datetime] = None
    location: Optional[str] = None


class EventOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    event_type: str
    start_at: datetime
    end_at: Optional[datetime]
    location: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: int
    title: str
    body: Optional[str]
    type: str
    link: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProPlanOut(BaseModel):
    id: int
    name: str
    duration_days: int
    price: Decimal
    description: Optional[str]

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    plan_id: int
    amount: Decimal
    screenshot_url: Optional[str] = None


class PaymentOut(BaseModel):
    id: int
    user_id: int
    plan_id: int
    amount: Decimal
    screenshot_url: Optional[str]
    status: str
    rejection_reason: Optional[str]
    created_at: datetime
    username: Optional[str] = None
    plan_name: Optional[str] = None

    class Config:
        from_attributes = True
