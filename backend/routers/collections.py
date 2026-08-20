from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.class_model import ClassMember
from backend.models.collection import (
    MoneyCollection, CollectionPayment,
    CollectionStatus, CollectionPaymentStatus
)
from backend.models.notification import Notification
from backend.models.chat import Chat, Message, ChatType
from backend.schemas.collection import (
    CollectionCreate, CollectionOut,
    CollectionPaymentCreate, CollectionPaymentOut
)
from backend.utils.security import get_current_active_user

router = APIRouter(prefix="/api/collections", tags=["collections"])


def _get_user_class_id(user: User, db: Session) -> int:
    membership = db.query(ClassMember).filter(ClassMember.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в классе")
    return membership.class_id


def _is_starosta_or_above(user: User) -> bool:
    return user.role in (UserRole.starosta, UserRole.moderator, UserRole.admin)


def _calc_progress(collected: Decimal, target: Decimal) -> float:
    if target <= 0:
        return 0.0
    pct = float(collected / target * 100)
    return min(round(pct, 1), 100.0)


def _collection_to_out(
    c: MoneyCollection,
    db: Session,
    current_user: User,
    show_details: bool = False
) -> CollectionOut:
    approved = db.query(CollectionPayment).filter(
        CollectionPayment.collection_id == c.id,
        CollectionPayment.status == CollectionPaymentStatus.approved
    ).count()
    total_payments = db.query(CollectionPayment).filter(
        CollectionPayment.collection_id == c.id
    ).count()

    user_pay = db.query(CollectionPayment).filter(
        CollectionPayment.collection_id == c.id,
        CollectionPayment.user_id == current_user.id
    ).order_by(CollectionPayment.created_at.desc()).first()

    creator = db.query(User).filter(User.id == c.created_by).first()

    return CollectionOut(
        id=c.id,
        title=c.title,
        description=c.description,
        target_amount=c.target_amount,
        suggested_amount=c.suggested_amount,
        payment_details=c.payment_details if show_details else None,
        status=c.status.value,
        collected_amount=c.collected_amount or Decimal("0"),
        progress_percent=_calc_progress(c.collected_amount or Decimal("0"), c.target_amount),
        created_by=c.created_by,
        creator_name=creator.display_name if creator else None,
        created_at=c.created_at,
        user_payment_status=user_pay.status.value if user_pay else None,
        payments_count=total_payments,
        approved_count=approved,
    )


@router.get("/", response_model=List[CollectionOut])
def list_collections(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    items = (
        db.query(MoneyCollection)
        .filter(MoneyCollection.class_id == class_id)
        .order_by(MoneyCollection.created_at.desc())
        .all()
    )
    return [_collection_to_out(c, db, current_user) for c in items]


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(
    collection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Сбор не найден")
    # Реквизиты видны всем участникам класса (закрытый класс)
    return _collection_to_out(c, db, current_user, show_details=True)


@router.post("/", response_model=CollectionOut)
def create_collection(
    data: CollectionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if not _is_starosta_or_above(current_user):
        raise HTTPException(status_code=403, detail="Только староста может создавать сборы")

    class_id = _get_user_class_id(current_user, db)

    c = MoneyCollection(
        class_id=class_id,
        created_by=current_user.id,
        title=data.title,
        description=data.description,
        target_amount=data.target_amount,
        suggested_amount=data.suggested_amount,
        payment_details=data.payment_details,
        status=CollectionStatus.active,
        collected_amount=Decimal("0"),
    )
    db.add(c)
    db.flush()

    # Системное сообщение в общий чат
    general = db.query(Chat).filter(
        Chat.class_id == class_id, Chat.chat_type == ChatType.general
    ).first()
    if general:
        msg = Message(
            chat_id=general.id,
            sender_id=current_user.id,
            content=(
                f"💰 Новый сбор: «{c.title}»\n"
                f"Нужно собрать: {c.target_amount} ₽\n"
                f"С одного: ~{c.suggested_amount} ₽\n"
                f"Откройте раздел «Сборы» и нажмите «Оплатить»"
            ),
        )
        db.add(msg)

    # Уведомления всем одноклассникам
    members = db.query(ClassMember).filter(ClassMember.class_id == class_id).all()
    for m in members:
        if m.user_id == current_user.id:
            continue
        db.add(Notification(
            user_id=m.user_id,
            title="Новый сбор денег",
            body=f"{current_user.display_name} создал(а) сбор «{c.title}» на {c.target_amount} ₽",
            type="collection",
            link=f"/collections/{c.id}",
        ))

    db.commit()
    db.refresh(c)
    return _collection_to_out(c, db, current_user, show_details=True)


@router.post("/{collection_id}/pay", response_model=CollectionPaymentOut)
def submit_payment(
    collection_id: int,
    data: CollectionPaymentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id,
        MoneyCollection.status == CollectionStatus.active
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Активный сбор не найден")

    # Нельзя платить повторно, пока предыдущая заявка pending
    existing = db.query(CollectionPayment).filter(
        CollectionPayment.collection_id == collection_id,
        CollectionPayment.user_id == current_user.id,
        CollectionPayment.status == CollectionPaymentStatus.pending
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="У вас уже есть заявка на проверке")

    payment = CollectionPayment(
        collection_id=collection_id,
        user_id=current_user.id,
        amount=data.amount,
        screenshot_url=data.screenshot_url,
        comment=data.comment,
        status=CollectionPaymentStatus.pending,
    )
    db.add(payment)

    # Уведомление старосте
    db.add(Notification(
        user_id=c.created_by,
        title="Новая оплата по сбору",
        body=f"{current_user.display_name} отправил(а) {data.amount} ₽ по сбору «{c.title}». Проверьте чек.",
        type="collection",
        link=f"/collections/{c.id}",
    ))

    db.commit()
    db.refresh(payment)

    return CollectionPaymentOut(
        id=payment.id,
        collection_id=payment.collection_id,
        user_id=payment.user_id,
        username=current_user.username,
        display_name=current_user.display_name,
        amount=payment.amount,
        screenshot_url=payment.screenshot_url,
        comment=payment.comment,
        status=payment.status.value,
        rejection_reason=None,
        created_at=payment.created_at,
        is_overpay=payment.amount > c.suggested_amount,
    )


@router.get("/{collection_id}/payments", response_model=List[CollectionPaymentOut])
def list_payments(
    collection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Сбор не найден")

    # Платежи видит создатель, староста, модератор, админ; обычный — только свои
    is_manager = c.created_by == current_user.id or _is_starosta_or_above(current_user)

    query = db.query(CollectionPayment).filter(CollectionPayment.collection_id == collection_id)
    if not is_manager:
        query = query.filter(CollectionPayment.user_id == current_user.id)

    payments = query.order_by(CollectionPayment.created_at.desc()).all()
    result = []
    for p in payments:
        u = db.query(User).filter(User.id == p.user_id).first()
        result.append(CollectionPaymentOut(
            id=p.id,
            collection_id=p.collection_id,
            user_id=p.user_id,
            username=u.username if u else None,
            display_name=u.display_name if u else None,
            amount=p.amount,
            screenshot_url=p.screenshot_url,
            comment=p.comment,
            status=p.status.value,
            rejection_reason=p.rejection_reason,
            created_at=p.created_at,
            is_overpay=p.amount > c.suggested_amount,
        ))
    return result


@router.post("/{collection_id}/payments/{payment_id}/approve")
def approve_payment(
    collection_id: int,
    payment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Сбор не найден")

    if c.created_by != current_user.id and not _is_starosta_or_above(current_user):
        raise HTTPException(status_code=403, detail="Только староста может одобрять платежи")

    payment = db.query(CollectionPayment).filter(
        CollectionPayment.id == payment_id,
        CollectionPayment.collection_id == collection_id,
        CollectionPayment.status == CollectionPaymentStatus.pending
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден или уже обработан")

    payment.status = CollectionPaymentStatus.approved
    payment.reviewed_by = current_user.id
    payment.reviewed_at = datetime.utcnow()

    # Обновляем собранную сумму
    c.collected_amount = (c.collected_amount or Decimal("0")) + payment.amount
    progress = _calc_progress(c.collected_amount, c.target_amount)

    if progress >= 100:
        c.status = CollectionStatus.completed

    payer = db.query(User).filter(User.id == payment.user_id).first()

    # Уведомление плательщику
    db.add(Notification(
        user_id=payment.user_id,
        title="Платёж одобрен",
        body=f"Ваш платёж {payment.amount} ₽ по сбору «{c.title}» подтверждён. Собрано: {progress}%",
        type="collection",
    ))

    # Если переплата — сообщение в общий чат
    if payment.amount > c.suggested_amount and payer:
        general = db.query(Chat).filter(
            Chat.class_id == class_id, Chat.chat_type == ChatType.general
        ).first()
        if general:
            over = payment.amount - c.suggested_amount
            db.add(Message(
                chat_id=general.id,
                sender_id=current_user.id,
                content=(
                    f"🎉 {payer.display_name} отправил(а) больше необходимой суммы "
                    f"по сбору «{c.title}» (+{over} ₽)!"
                ),
            ))
        # Уведомление всем
        members = db.query(ClassMember).filter(ClassMember.class_id == class_id).all()
        for m in members:
            if m.user_id == payment.user_id:
                continue
            db.add(Notification(
                user_id=m.user_id,
                title="Переплата в сборе",
                body=f"{payer.display_name} отправил(а) больше суммы по сбору «{c.title}»",
                type="collection",
            ))

    # Если сбор завершён
    if c.status == CollectionStatus.completed:
        general = db.query(Chat).filter(
            Chat.class_id == class_id, Chat.chat_type == ChatType.general
        ).first()
        if general:
            db.add(Message(
                chat_id=general.id,
                sender_id=current_user.id,
                content=f"✅ Сбор «{c.title}» полностью собран! 100%",
            ))

    db.commit()
    return {
        "message": "Платёж одобрен",
        "collected_amount": float(c.collected_amount),
        "progress_percent": progress,
        "status": c.status.value,
    }


@router.post("/{collection_id}/payments/{payment_id}/reject")
def reject_payment(
    collection_id: int,
    payment_id: int,
    reason: str = Query("Чек не подтверждён"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Сбор не найден")

    if c.created_by != current_user.id and not _is_starosta_or_above(current_user):
        raise HTTPException(status_code=403, detail="Только староста может отклонять платежи")

    payment = db.query(CollectionPayment).filter(
        CollectionPayment.id == payment_id,
        CollectionPayment.collection_id == collection_id,
        CollectionPayment.status == CollectionPaymentStatus.pending
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден или уже обработан")

    payment.status = CollectionPaymentStatus.rejected
    payment.rejection_reason = reason
    payment.reviewed_by = current_user.id
    payment.reviewed_at = datetime.utcnow()

    db.add(Notification(
        user_id=payment.user_id,
        title="Платёж отклонён",
        body=f"Ваш платёж по сбору «{c.title}» отклонён. Причина: {reason}",
        type="collection",
    ))
    db.commit()
    return {"message": "Платёж отклонён"}


@router.post("/{collection_id}/close")
def close_collection(
    collection_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    class_id = _get_user_class_id(current_user, db)
    c = db.query(MoneyCollection).filter(
        MoneyCollection.id == collection_id,
        MoneyCollection.class_id == class_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Сбор не найден")
    if c.created_by != current_user.id and not _is_starosta_or_above(current_user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    c.status = CollectionStatus.closed
    c.closed_at = datetime.utcnow()
    db.commit()
    return {"message": "Сбор закрыт"}
