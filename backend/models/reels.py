from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Float
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Reel(Base):
    __tablename__ = "reels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_url = Column(String(500), nullable=False)
    media_type = Column(String(20), default="image")  # image | video
    caption = Column(Text, default="")
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User", foreign_keys=[user_id])
    likes = relationship("ReelLike", back_populates="reel", cascade="all, delete-orphan")
    comments = relationship("ReelComment", back_populates="reel", cascade="all, delete-orphan")
    views = relationship("ReelView", back_populates="reel", cascade="all, delete-orphan")


class ReelLike(Base):
    __tablename__ = "reel_likes"
    __table_args__ = (UniqueConstraint("reel_id", "user_id", name="uq_reel_like"),)

    id = Column(Integer, primary_key=True)
    reel_id = Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    reel = relationship("Reel", back_populates="likes")


class ReelComment(Base):
    __tablename__ = "reel_comments"

    id = Column(Integer, primary_key=True)
    reel_id = Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    is_gift = Column(Boolean, default=False)
    gift_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    reel = relationship("Reel", back_populates="comments")
    author = relationship("User", foreign_keys=[user_id])


class ReelView(Base):
    __tablename__ = "reel_views"
    __table_args__ = (UniqueConstraint("reel_id", "user_id", name="uq_reel_view"),)

    id = Column(Integer, primary_key=True)
    reel_id = Column(Integer, ForeignKey("reels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    reel = relationship("Reel", back_populates="views")


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uq_follow"),)

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CoinPackage(Base):
    __tablename__ = "coin_packages"

    id = Column(Integer, primary_key=True)
    amount = Column(Integer, nullable=False)  # coins
    price_smn = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CoinOrder(Base):
    """Buy coins or withdraw request."""
    __tablename__ = "coin_orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_type = Column(String(20), nullable=False)  # buy | withdraw
    coins = Column(Integer, nullable=False)
    amount_smn = Column(Float, nullable=False)
    status = Column(String(20), default="pending")  # pending | approved | rejected
    screenshot_url = Column(String(500), nullable=True)
    card_number = Column(String(100), nullable=True)
    bank_name = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CoinLedger(Base):
    __tablename__ = "coin_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delta = Column(Integer, nullable=False)  # +buy / gift in, -gift out / withdraw
    reason = Column(String(50), nullable=False)
    ref_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
