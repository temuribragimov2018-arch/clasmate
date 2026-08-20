from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.class_model import Class, ClassMember
from backend.models.pro import ProPlan, Payment, ProSubscription, PaymentStatus
from backend.models.notification import Notification
from backend.models.admin_log import AdminActionLog
from backend.models.chat import Chat, ChatMember, ChatType
from backend.schemas.user import UserOut
from backend.schemas.common import PaymentOut, ProPlanOut
from backend.utils.security import require_admin
from backend.config import get_settings
import secrets

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


def log_action(db: Session, admin_id: int, action: str, target_type: str = None, target_id: int = None, details: str = None):
    log = AdminActionLog(
        admin_id=admin_id, action=action, target_type=target_type,
        target_id=target_id, details=details
    )
    db.add(log)
    db.commit()


@router.get("/users", response_model=List[UserOut])
def list_users(
    search: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = db.query(User)
    if search:
        query = query.filter(or_(User.username.ilike(f"%{search}%"), User.display_name.ilike(f"%{search}%")))
    return query.order_by(User.created_at.desc()).limit(100).all()


@router.post("/users/{user_id}/block")
def block_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    log_action(db, admin.id, "block_user", "user", user_id)
    return {"message": "User blocked"}


@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    log_action(db, admin.id, "unblock_user", "user", user_id)
    return {"message": "User unblocked"}


@router.put("/users/{user_id}/role")
def change_role(user_id: int, role: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role if isinstance(role, str) else getattr(role, "value", str(role))
    db.commit()
    log_action(db, admin.id, "change_role", "user", user_id, f"New role: {role}")
    return {"message": "Role updated"}


@router.post("/invite-code")
def create_invite_code(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    # Get or create default class
    cls = db.query(Class).first()
    if not cls:
        code = secrets.token_hex(4).upper()
        cls = Class(name="Класс 1", invite_code=code)
        db.add(cls)
        db.flush()
        # Create general chat
        chat = Chat(name="Общий чат", chat_type="general", class_id=cls.id)
        db.add(chat)
        db.commit()
        return {"invite_code": code, "class_id": cls.id}
    new_code = secrets.token_hex(4).upper()
    cls.invite_code = new_code
    db.commit()
    log_action(db, admin.id, "create_invite_code", "class", cls.id, new_code)
    return {"invite_code": new_code}


@router.get("/payments", response_model=List[PaymentOut])
def list_payments(
    status: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Payment)
    if status:
        query = query.filter(Payment.status == str(status))
    payments = query.order_by(Payment.created_at.desc()).all()
    result = []
    for p in payments:
        user = db.query(User).filter(User.id == p.user_id).first()
        plan = db.query(ProPlan).filter(ProPlan.id == p.plan_id).first()
        result.append(PaymentOut(
            id=p.id, user_id=p.user_id, plan_id=p.plan_id, amount=p.amount,
            screenshot_url=p.screenshot_url, status=(p.status.value if hasattr(p.status, "value") else str(p.status)),
            rejection_reason=p.rejection_reason, created_at=p.created_at,
            username=user.username if user else None,
            plan_name=plan.name if plan else None
        ))
    return result


@router.post("/payments/{payment_id}/approve")
def approve_payment(payment_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    st = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
    if st != "pending":
        raise HTTPException(status_code=400, detail="Already processed")

    plan = db.query(ProPlan).filter(ProPlan.id == payment.plan_id).first()
    user = db.query(User).filter(User.id == payment.user_id).first()

    payment.status = "approved"
    payment.reviewed_by = admin.id
    payment.reviewed_at = datetime.utcnow()

    starts = datetime.utcnow()
    if user.is_pro and user.pro_until and user.pro_until > starts:
        starts = user.pro_until
    ends = starts + timedelta(days=plan.duration_days)

    sub = ProSubscription(
        user_id=user.id, plan_id=plan.id, payment_id=payment.id,
        starts_at=starts, ends_at=ends, is_active=True
    )
    db.add(sub)
    user.is_pro = True
    user.pro_until = ends

    notif = Notification(
        user_id=user.id,
        title="PRO активирован!",
        body=f"Ваша подписка ClassMate PRO активна до {ends.strftime('%d.%m.%Y')}",
        type="pro"
    )
    db.add(notif)
    db.commit()
    log_action(db, admin.id, "approve_payment", "payment", payment_id)
    return {"message": "Payment approved", "pro_until": ends}


@router.post("/payments/{payment_id}/reject")
def reject_payment(
    payment_id: int,
    reason: str = "Недостаточно данных",
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if str(getattr(payment.status, "value", payment.status)) != "pending":
        raise HTTPException(status_code=400, detail="Already processed")

    payment.status = "rejected"
    payment.rejection_reason = reason
    payment.reviewed_by = admin.id
    payment.reviewed_at = datetime.utcnow()

    notif = Notification(
        user_id=payment.user_id,
        title="Платёж отклонён",
        body=f"Причина: {reason}",
        type="pro"
    )
    db.add(notif)
    db.commit()
    log_action(db, admin.id, "reject_payment", "payment", payment_id, reason)
    return {"message": "Payment rejected"}


@router.get("/plans", response_model=List[ProPlanOut])
def admin_plans(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(ProPlan).all()


@router.put("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    price: float,
    duration_days: int = None,
    name: str = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    plan = db.query(ProPlan).filter(ProPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.price = price
    if duration_days:
        plan.duration_days = duration_days
    if name:
        plan.name = name
    db.commit()
    log_action(db, admin.id, "update_plan", "pro_plan", plan_id)
    return {"message": "Plan updated"}


@router.get("/stats")
def stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "active_users": db.query(User).filter(User.is_active == True).count(),
        "pro_users": db.query(User).filter(User.is_pro == True).count(),
        "pending_payments": db.query(Payment).filter(Payment.status == "pending").count(),
    }


@router.get("/logs")
def action_logs(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(AdminActionLog).order_by(AdminActionLog.created_at.desc()).limit(100).all()
    return [
        {
            "id": l.id, "admin_id": l.admin_id, "action": l.action,
            "target_type": l.target_type, "target_id": l.target_id,
            "details": l.details, "created_at": l.created_at
        } for l in logs
    ]


@router.get("/classes")
def list_classes(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    classes = db.query(Class).order_by(Class.id.desc()).all()
    out = []
    for c in classes:
        members = db.query(ClassMember).filter(ClassMember.class_id == c.id).count()
        out.append({
            "id": c.id,
            "name": c.name,
            "invite_code": c.invite_code,
            "description": c.description,
            "members": members,
            "is_active": c.is_active,
        })
    return out


@router.post("/classes")
def create_class(
    name: str = Query(...),
    invite_code: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create class + general chat + starosta account + join staff chat."""
    from backend.utils.security import get_password_hash
    import re
    code = (invite_code or secrets.token_hex(4)).upper().strip()
    if db.query(Class).filter(Class.invite_code == code).first():
        raise HTTPException(400, "Такой код приглашения уже есть")

    cls = Class(name=name.strip(), description="", invite_code=code, is_active=True)
    db.add(cls)
    db.flush()

    gen = Chat(name=f"Чат класса {name.strip()}", chat_type="general", class_id=cls.id, created_by=admin.id)
    db.add(gen)
    db.flush()

    # Auto starosta username from class name
    base = re.sub(r"[^a-z0-9]+", "", name.lower())[:12] or "class"
    uname = f"starosta_{base}"
    i = 1
    while db.query(User).filter(User.username == uname).first():
        uname = f"starosta_{base}{i}"
        i += 1
    pwd = secrets.token_hex(3)  # 6 hex chars
    starosta = User(
        username=uname,
        hashed_password=get_password_hash(pwd),
        display_name=f"Староста {name.strip()}",
        role="starosta",
        is_active=True,
    )
    db.add(starosta)
    db.flush()
    db.add(ClassMember(user_id=starosta.id, class_id=cls.id))
    db.add(ChatMember(chat_id=gen.id, user_id=starosta.id))

    # Staff chat: admin + all starostas
    staff = db.query(Chat).filter(Chat.chat_type == "staff").first()
    if not staff:
        staff = Chat(name="Чат Админ ↔ Старосты", chat_type="staff", class_id=None, created_by=admin.id)
        db.add(staff)
        db.flush()
        db.add(ChatMember(chat_id=staff.id, user_id=admin.id))
    if not db.query(ChatMember).filter(ChatMember.chat_id == staff.id, ChatMember.user_id == starosta.id).first():
        db.add(ChatMember(chat_id=staff.id, user_id=starosta.id))
    if not db.query(ChatMember).filter(ChatMember.chat_id == staff.id, ChatMember.user_id == admin.id).first():
        db.add(ChatMember(chat_id=staff.id, user_id=admin.id))

    db.commit()
    log_action(db, admin.id, "create_class", "class", cls.id, f"{name} / {code} / {uname}")
    return {
        "id": cls.id,
        "name": cls.name,
        "invite_code": code,
        "starosta_username": uname,
        "starosta_password": pwd,
        "message": f"Класс создан. Староста: {uname} / {pwd}",
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "admin" or (hasattr(user.role, "value") and user.role.value == "admin"):
        raise HTTPException(400, "Cannot delete admin")
    db.delete(user)
    db.commit()
    log_action(db, admin.id, "delete_user", "user", user_id)
    return {"message": "Deleted"}


@router.post("/users/{user_id}/grant-pro")
def grant_pro(user_id: int, days: int = 30, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    now = datetime.utcnow()
    base = user.pro_until if (user.is_pro and user.pro_until and user.pro_until > now) else now
    user.pro_until = base + timedelta(days=days)
    user.is_pro = True
    db.commit()
    log_action(db, admin.id, "grant_pro", "user", user_id, f"{days}d")
    return {"message": "PRO granted", "pro_until": user.pro_until}


@router.post("/broadcast")
def broadcast(data: dict, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    title = (data.get("title") or "Объявление администрации").strip()
    body = (data.get("body") or "").strip()
    users = db.query(User).filter(User.is_active == True).all()
    for u in users:
        db.add(Notification(
            user_id=u.id,
            title=title,
            body=body,
            type="broadcast",
        ))
    db.commit()
    log_action(db, admin.id, "broadcast", details=title)
    return {"message": f"Sent to {len(users)} users"}


# Simple key-value settings stored in first admin's privacy_settings JSON is bad;
# use a minimal AppSettings via Class description hack or Notification - better: file/env
# Use a Class with invite_code=__SETTINGS__ or store in AdminActionLog - use Class model side table
# Simplest: environment-like table via dict in memory + DB Class special row

_SETTINGS_CACHE = {"instagram_url": "https://instagram.com/", "payment_details": "Оплата на карту. Укажите User ID в комментарии."}

@router.get("/settings")
def get_settings_admin(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(Class).filter(Class.invite_code == "__APP_SETTINGS__").first()
    if row and row.description:
        try:
            import json
            data = json.loads(row.description)
            _SETTINGS_CACHE.update(data)
        except Exception:
            pass
    return dict(_SETTINGS_CACHE)


@router.put("/settings")
def put_settings(data: dict, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    import json
    _SETTINGS_CACHE.update({k: v for k, v in data.items() if k in ("instagram_url", "payment_details", "coin_price_smn", "coin_rate_out")})
    row = db.query(Class).filter(Class.invite_code == "__APP_SETTINGS__").first()
    if not row:
        row = Class(name="__settings__", invite_code="__APP_SETTINGS__", description=json.dumps(_SETTINGS_CACHE), is_active=False)
        db.add(row)
    else:
        row.description = json.dumps(_SETTINGS_CACHE)
    db.commit()
    return dict(_SETTINGS_CACHE)



@router.post("/system-reset")
def system_reset(
    confirm: str = Query("NO"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Полный сброс. Остаётся только admin. confirm=RESET"""
    if confirm != "RESET":
        raise HTTPException(400, "Передайте confirm=RESET")

    from sqlalchemy import text, inspect as sa_inspect
    from backend.database import engine
    from backend.models.user import User
    from backend.utils.security import get_password_hash

    # сохранить пароль admin
    admin_row = db.query(User).filter(User.username == "admin").first()
    admin_hash = admin_row.hashed_password if admin_row else get_password_hash("admin123")
    admin_display = (admin_row.display_name if admin_row else None) or "Администратор"

    # сбросить возможную aborted-транзакцию сессии
    try:
        db.rollback()
    except Exception:
        pass

    tables = [
        "reel_comments", "reel_likes", "reel_views", "reels", "follows",
        "coin_ledger", "coin_orders", "coin_packages",
        "reactions", "messages", "chat_members", "chats",
        "homework_user_statuses", "homeworks", "schedules", "announcements",
        "poll_votes", "poll_options", "polls", "events",
        "collection_payments", "money_collections",
        "notifications", "payments", "pro_subscriptions", "files",
        "class_members", "classes", "admin_action_logs",
    ]

    errors = []
    try:
        dialect = engine.dialect.name

        if dialect == "postgresql":
            # AUTOCOMMIT — TRUNCATE не зависит от aborted session
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                insp = sa_inspect(engine)
                have = set(insp.get_table_names())
                to_trunc = [x for x in tables if x in have]
                if to_trunc:
                    names = ", ".join(f'"{x}"' for x in to_trunc)
                    conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
                # users кроме admin
                if "users" in have:
                    conn.execute(text("DELETE FROM users WHERE username <> 'admin'"))
        else:
            for tbl in tables:
                try:
                    db.execute(text(f"DELETE FROM {tbl}"))
                    db.commit()
                except Exception as e:
                    db.rollback()
                    errors.append(f"{tbl}: {e}")
            try:
                db.execute(text("DELETE FROM users WHERE username != 'admin'"))
                db.commit()
            except Exception as e:
                db.rollback()
                errors.append(str(e))

        # свежая сессия: убедиться что admin на месте
        try:
            db.rollback()
        except Exception:
            pass
        db.expire_all()

        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                display_name=admin_display,
                hashed_password=admin_hash,
                role="admin",
                is_active=True,
                is_pro=True,
            )
            db.add(admin_user)
        else:
            admin_user.display_name = admin_display
            admin_user.hashed_password = admin_hash
            admin_user.role = "admin"
            admin_user.is_active = True
            admin_user.is_pro = True
            admin_user.pro_until = None
            for attr, val in [
                ("coin_balance", 0), ("coin_purchased", 0),
                ("followers_count", 0), ("following_count", 0), ("posts_count", 0),
            ]:
                if hasattr(admin_user, attr):
                    setattr(admin_user, attr, val)
            admin_user.avatar_url = None
            if hasattr(admin_user, "status"):
                admin_user.status = None
        db.commit()

        return {
            "ok": True,
            "message": "Система сброшена. Остался только admin. Создайте классы заново.",
            "errors": errors[:5] if errors else [],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Ошибка сброса: {e}")
