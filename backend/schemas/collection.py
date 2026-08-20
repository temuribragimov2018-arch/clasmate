from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal


class CollectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    target_amount: Decimal = Field(..., gt=0)
    suggested_amount: Decimal = Field(..., gt=0)
    payment_details: str = Field(..., min_length=5)


class CollectionOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    target_amount: Decimal
    suggested_amount: Decimal
    payment_details: Optional[str] = None  # скрываем до нажатия «Оплатить»
    status: str
    collected_amount: Decimal
    progress_percent: float = 0.0
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    user_payment_status: Optional[str] = None  # pending / approved / rejected / None
    payments_count: int = 0
    approved_count: int = 0

    class Config:
        from_attributes = True


class CollectionPaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    screenshot_url: Optional[str] = None
    comment: Optional[str] = None


class CollectionPaymentOut(BaseModel):
    id: int
    collection_id: int
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    amount: Decimal
    screenshot_url: Optional[str]
    comment: Optional[str]
    status: str
    rejection_reason: Optional[str]
    created_at: datetime
    is_overpay: bool = False

    class Config:
        from_attributes = True
