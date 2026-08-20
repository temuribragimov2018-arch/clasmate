from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    invite_code = Column(String(20), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = relationship("ClassMember", back_populates="class_", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="class_", cascade="all, delete-orphan")
    homeworks = relationship("Homework", back_populates="class_", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="class_", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="class_", cascade="all, delete-orphan")
    polls = relationship("Poll", back_populates="class_", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="class_", cascade="all, delete-orphan")
    files = relationship("File", back_populates="class_", cascade="all, delete-orphan")


class ClassMember(Base):
    __tablename__ = "class_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="class_memberships")
    class_ = relationship("Class", back_populates="members")
