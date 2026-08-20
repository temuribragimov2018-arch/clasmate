from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.announcement import Announcement
from backend.schemas.common import AnnouncementCreate, AnnouncementOut
from backend.utils.security import get_current_active_user, require_moderator_or_admin

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


@router.get("/", response_model=List[AnnouncementOut])
@router.get("", response_model=List[AnnouncementOut], include_in_schema=False)
def list_announcements(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    items = db.query(Announcement).filter(
        Announcement.class_id == membership.class_id
    ).order_by(Announcement.is_pinned.desc(), Announcement.is_important.desc(), Announcement.created_at.desc()).all()
    return items


@router.post("/", response_model=AnnouncementOut)
@router.post("", response_model=AnnouncementOut, include_in_schema=False)
def create_announcement(
    data: AnnouncementCreate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не привязаны к классу. Обратитесь к админу.")
    item = Announcement(
        class_id=membership.class_id,
        title=data.title,
        content=data.content,
        image_url=data.image_url,
        is_pinned=data.is_pinned,
        is_important=data.is_important,
        created_by=current_user.id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
