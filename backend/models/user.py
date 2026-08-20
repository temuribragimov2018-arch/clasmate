from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class UserRole(str, enum.Enum):
    student = "student"
    starosta = "starosta"
    moderator = "moderator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    status = Column(String(150), default="")
    role = Column(String(20), default=UserRole.student.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_pro = Column(Boolean, default=False)
    pro_until = Column(DateTime, nullable=True)
    theme = Column(String(50), default="light")
    custom_colors = Column(Text, nullable=True)  # JSON string for PRO
    privacy_settings = Column(Text, nullable=True)  # JSON
    streak = Column(Integer, default=0)
    coin_balance = Column(Integer, default=0)
    coin_purchased = Column(Integer, default=0)  # cannot withdraw these
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    monetization_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (foreign_keys required where multiple FKs to users exist)
    class_memberships = relationship("ClassMember", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    payments = relationship(
        "Payment",
        back_populates="user",
        foreign_keys="Payment.user_id",
        cascade="all, delete-orphan",
    )
    reviewed_payments = relationship(
        "Payment",
        foreign_keys="Payment.reviewed_by",
        back_populates="reviewer",
    )
    subscriptions = relationship("ProSubscription", back_populates="user", cascade="all, delete-orphan")
    poll_votes = relationship("PollVote", back_populates="user", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="user", cascade="all, delete-orphan")
    admin_logs = relationship("AdminActionLog", back_populates="admin", foreign_keys="AdminActionLog.admin_id")

    def __repr__(self):
        return f"<User {self.username}>"
