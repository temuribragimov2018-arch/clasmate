from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from backend.database import get_db
from backend.models.user import User
from backend.models.reels import CoinPackage, CoinOrder, CoinLedger
from backend.models.class_model import Class
from backend.utils.security import get_current_active_user, require_admin
import json

router = APIRouter(prefix="/api/coins", tags=["coins"])


def _settings(db: Session) -> dict:
    defaults = {"coin_price_smn": 1.0, "coin_rate_out": 1.0, "payment_details": "Оплата на карту. Укажите User ID."}
    row = db.query(Class).filter(Class.invite_code == "__APP_SETTINGS__").first()
    if row and row.description:
        try:
            defaults.update(json.loads(row.description))
        except Exception:
            pass
    return defaults


@router.get("/balance")
def balance(current_user: User = Depends(get_current_active_user)):
    return {
        "balance": current_user.coin_balance or 0,
        "purchased": current_user.coin_purchased or 0,
        "withdrawable": max(0, (current_user.coin_balance or 0) - (current_user.coin_purchased or 0)),
    }


@router.get("/packages")
def packages(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    pkgs = db.query(CoinPackage).filter(CoinPackage.is_active == True).order_by(CoinPackage.amount).all()
    if not pkgs:
        # defaults
        return [
            {"id": 0, "amount": 10, "price_smn": 10},
            {"id": 0, "amount": 50, "price_smn": 50},
            {"id": 0, "amount": 100, "price_smn": 100},
            {"id": 0, "amount": 500, "price_smn": 500},
        ]
    return [{"id": p.id, "amount": p.amount, "price_smn": float(p.price_smn)} for p in pkgs]


class BuyRequest(BaseModel):
    coins: int = Field(..., ge=10)
    screenshot_url: Optional[str] = None


@router.post("/buy")
def buy_coins(data: BuyRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    cfg = _settings(db)
    rate = float(cfg.get("coin_price_smn") or 1)
    amount_smn = data.coins * rate
    order = CoinOrder(
        user_id=current_user.id,
        order_type="buy",
        coins=data.coins,
        amount_smn=amount_smn,
        screenshot_url=data.screenshot_url,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "coins": order.coins, "amount_smn": order.amount_smn, "status": "pending", "message": "Заявка отправлена админу"}


class WithdrawRequest(BaseModel):
    coins: int = Field(..., ge=500)
    card_number: str = Field(..., min_length=4)
    bank_name: str = Field(..., min_length=2)


@router.post("/withdraw")
def withdraw(data: WithdrawRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    cfg = _settings(db)
    rate = float(cfg.get("coin_rate_out") or 1)
    bal = current_user.coin_balance or 0
    purchased = current_user.coin_purchased or 0
    withdrawable = max(0, bal - purchased)
    if data.coins > withdrawable:
        raise HTTPException(400, f"Можно вывести не больше {withdrawable} (купленные монеты не выводятся)")
    if data.coins < 500:
        raise HTTPException(400, "Минимум 500 монет")
    amount_smn = data.coins * rate
    order = CoinOrder(
        user_id=current_user.id,
        order_type="withdraw",
        coins=data.coins,
        amount_smn=amount_smn,
        card_number=data.card_number,
        bank_name=data.bank_name,
        status="pending",
    )
    # hold coins
    current_user.coin_balance = bal - data.coins
    db.add(CoinLedger(user_id=current_user.id, delta=-data.coins, reason="withdraw_hold"))
    db.add(order)
    db.commit()
    return {"id": order.id, "amount_smn": amount_smn, "status": "pending"}


@router.get("/orders/my")
def my_orders(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    rows = db.query(CoinOrder).filter(CoinOrder.user_id == current_user.id).order_by(CoinOrder.created_at.desc()).limit(50).all()
    return [
        {"id": o.id, "type": o.order_type, "coins": o.coins, "amount_smn": o.amount_smn, "status": o.status, "created_at": o.created_at}
        for o in rows
    ]


# --- Admin ---
@router.get("/admin/orders")
def admin_orders(status: str = "pending", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(CoinOrder)
    if status:
        q = q.filter(CoinOrder.status == status)
    rows = q.order_by(CoinOrder.created_at.desc()).limit(100).all()
    out = []
    for o in rows:
        u = db.query(User).filter(User.id == o.user_id).first()
        out.append({
            "id": o.id, "type": o.order_type, "coins": o.coins, "amount_smn": o.amount_smn,
            "status": o.status, "screenshot_url": o.screenshot_url,
            "card_number": o.card_number, "bank_name": o.bank_name,
            "username": u.username if u else None, "created_at": o.created_at,
        })
    return out


@router.post("/admin/orders/{order_id}/approve")
def approve_order(order_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    o = db.query(CoinOrder).filter(CoinOrder.id == order_id).first()
    if not o or o.status != "pending":
        raise HTTPException(404, "Заявка не найдена")
    user = db.query(User).filter(User.id == o.user_id).first()
    if not user:
        raise HTTPException(404, "User")
    if o.order_type == "buy":
        user.coin_balance = (user.coin_balance or 0) + o.coins
        user.coin_purchased = (user.coin_purchased or 0) + o.coins
        db.add(CoinLedger(user_id=user.id, delta=o.coins, reason="buy", ref_id=o.id))
    # withdraw: coins already held
    o.status = "approved"
    o.reviewed_by = admin.id
    db.commit()
    return {"message": "Одобрено"}


@router.post("/admin/orders/{order_id}/reject")
def reject_order(order_id: int, reason: str = "", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    o = db.query(CoinOrder).filter(CoinOrder.id == order_id).first()
    if not o or o.status != "pending":
        raise HTTPException(404, "Заявка не найдена")
    user = db.query(User).filter(User.id == o.user_id).first()
    if o.order_type == "withdraw" and user:
        user.coin_balance = (user.coin_balance or 0) + o.coins  # return hold
        db.add(CoinLedger(user_id=user.id, delta=o.coins, reason="withdraw_reject", ref_id=o.id))
    o.status = "rejected"
    o.rejection_reason = reason
    o.reviewed_by = admin.id
    db.commit()
    return {"message": "Отклонено"}


@router.get("/admin/packages")
def admin_packages(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": p.id, "amount": p.amount, "price_smn": float(p.price_smn), "is_active": p.is_active}
            for p in db.query(CoinPackage).order_by(CoinPackage.amount).all()]


@router.post("/admin/packages")
def set_package(amount: int, price_smn: float, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.query(CoinPackage).filter(CoinPackage.amount == amount).first()
    if p:
        p.price_smn = price_smn
        p.is_active = True
    else:
        p = CoinPackage(amount=amount, price_smn=price_smn)
        db.add(p)
    db.commit()
    return {"ok": True}
