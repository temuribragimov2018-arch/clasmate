from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.schemas.user import UserOut, UserUpdate
from backend.utils.security import get_current_active_user

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/classmates", response_model=List[UserOut])
def get_classmates(
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Find user's class
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []

    query = (
        db.query(User)
        .join(ClassMember, ClassMember.user_id == User.id)
        .filter(ClassMember.class_id == membership.class_id, User.is_active == True)
    )
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%")
            )
        )
    users = query.order_by(User.is_online.desc(), User.display_name).all()
    return users


@router.get("/online")
def get_online_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    users = (
        db.query(User)
        .join(ClassMember, ClassMember.user_id == User.id)
        .filter(
            ClassMember.class_id == membership.class_id,
            User.is_online == True,
            User.is_active == True
        )
        .all()
    )
    return [{"id": u.id, "username": u.username, "display_name": u.display_name, "avatar_url": u.avatar_url} for u in users]


@router.put("/me", response_model=UserOut)
def update_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.status is not None:
        current_user.status = data.status
    if data.theme is not None:
        current_user.theme = data.theme
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
