from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey,
    Enum as SAEnum, Numeric
)
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class CollectionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    closed = "closed"


class CollectionPaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class MoneyCollection(Base):
    """Сбор денег, который создаёт только староста."""
    __tablename__ = "money_collections"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Сколько всего нужно собрать
    target_amount = Column(Numeric(12, 2), nullable=False)
    # Рекомендуемая сумма с одного человека (можно платить больше)
    suggested_amount = Column(Numeric(12, 2), nullable=False)

    # Реквизиты старосты
    payment_details = Column(Text, nullable=False)

    status = Column(SAEnum(CollectionStatus), default=CollectionStatus.active)
    # Кэшированная сумма одобренных платежей
    collected_amount = Column(Numeric(12, 2), default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])
    payments = relationship("CollectionPayment", back_populates="collection", cascade="all, delete-orphan")


class CollectionPayment(Base):
    """Платёж одноклассника в сбор."""
    __tablename__ = "collection_payments"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("money_collections.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    screenshot_url = Column(String(500), nullable=True)
    comment = Column(Text, nullable=True)

    status = Column(SAEnum(CollectionPaymentStatus), default=CollectionPaymentStatus.pending)
    rejection_reason = Column(Text, nullable=True)

    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    collection = relationship("MoneyCollection", back_populates="payments")
    user = relationship("User", foreign_keys=[user_id])
