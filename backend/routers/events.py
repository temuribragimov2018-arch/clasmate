from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.event import Event
from backend.schemas.common import EventCreate, EventOut
from backend.utils.security import get_current_active_user, require_moderator_or_admin

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/", response_model=List[EventOut])
@router.get("", response_model=List[EventOut], include_in_schema=False)
def list_events(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    items = db.query(Event).filter(Event.class_id == membership.class_id).order_by(Event.start_at).all()
    return items


@router.post("/", response_model=EventOut)
@router.post("", response_model=EventOut, include_in_schema=False)
def create_event(
    data: EventCreate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не привязаны к классу. Обратитесь к админу.")
    item = Event(
        class_id=membership.class_id,
        title=data.title,
        description=data.description,
        event_type=data.event_type,
        start_at=data.start_at,
        end_at=data.end_at,
        location=data.location,
        created_by=current_user.id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
