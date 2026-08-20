from datetime import datetime, timedelta
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlalchemy.orm import Session
import os
import uuid
from backend.database import get_db
from backend.models.user import User
from backend.models.pro import ProPlan, Payment, ProSubscription, PaymentStatus
from backend.models.notification import Notification
from backend.models.admin_log import AdminActionLog
from backend.schemas.common import ProPlanOut, PaymentCreate, PaymentOut
from backend.utils.security import get_current_active_user, require_admin
from backend.config import get_settings

router = APIRouter(prefix="/api/pro", tags=["pro"])
settings = get_settings()


@router.get("/plans", response_model=List[ProPlanOut])
def list_plans(db: Session = Depends(get_db)):
    return db.query(ProPlan).filter(ProPlan.is_active == True).all()


@router.get("/payment-details")
def payment_details(current_user: User = Depends(get_current_active_user)):
    return {
        "details": settings.PAYMENT_DETAILS,
        "user_id": current_user.id,
        "instruction": "Переведите сумму на указанные реквизиты. В комментарии укажите ClassMate PRO и ваш user_id. Затем загрузите скриншот чека."
    }


@router.post("/payments", response_model=PaymentOut)
def create_payment(
    data: PaymentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    plan = db.query(ProPlan).filter(ProPlan.id == data.plan_id, ProPlan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    payment = Payment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount=data.amount,
        screenshot_url=data.screenshot_url,
        status="pending"
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return PaymentOut(
        id=payment.id, user_id=payment.user_id, plan_id=payment.plan_id,
        amount=payment.amount, screenshot_url=payment.screenshot_url,
        status=(payment.status.value if hasattr(payment.status,"value") else str(payment.status)), rejection_reason=None, created_at=payment.created_at
    )


@router.get("/my-payments", response_model=List[PaymentOut])
def my_payments(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).order_by(Payment.created_at.desc()).all()
    return [
        PaymentOut(
            id=p.id, user_id=p.user_id, plan_id=p.plan_id, amount=p.amount,
            screenshot_url=p.screenshot_url, status=(p.status.value if hasattr(p.status,"value") else str(p.status)),
            rejection_reason=p.rejection_reason, created_at=p.created_at
        ) for p in payments
    ]


@router.get("/status")
def pro_status(current_user: User = Depends(get_current_active_user)):
    return {
        "is_pro": current_user.is_pro,
        "pro_until": current_user.pro_until,
        "active": current_user.is_pro and current_user.pro_until and current_user.pro_until > datetime.utcnow()
    }


@router.post("/social-bonus")
def social_bonus(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Grant 2 days PRO after social subscribe claim (once per user via privacy_settings flag)."""
    from datetime import timedelta
    flags = current_user.privacy_settings or ""
    if "social_bonus_claimed" in flags:
        raise HTTPException(400, "Бонус уже получен")
    now = datetime.utcnow()
    base = current_user.pro_until if (current_user.is_pro and current_user.pro_until and current_user.pro_until > now) else now
    current_user.pro_until = base + timedelta(days=2)
    current_user.is_pro = True
    current_user.privacy_settings = (flags + "|social_bonus_claimed").strip("|")
    db.commit()
    return {"message": "PRO на 2 дня активирован!", "pro_until": current_user.pro_until}


@router.post("/social-skip")
def social_skip(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    flags = current_user.privacy_settings or ""
    if "social_modal_seen" not in flags:
        current_user.privacy_settings = (flags + "|social_modal_seen").strip("|")
        db.commit()
    return {"message": "ok"}

