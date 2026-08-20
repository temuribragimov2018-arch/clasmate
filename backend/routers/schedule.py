from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.schedule import Schedule
from backend.schemas.common import ScheduleCreate, ScheduleOut
from backend.utils.security import get_current_active_user, require_moderator_or_admin

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/", response_model=List[ScheduleOut])
@router.get("", response_model=List[ScheduleOut], include_in_schema=False)
def get_schedule(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    items = db.query(Schedule).filter(Schedule.class_id == membership.class_id).order_by(
        Schedule.day_of_week, Schedule.lesson_number
    ).all()
    out = []
    for s in items:
        out.append({
            "id": s.id,
            "day_of_week": s.day_of_week,
            "lesson_number": s.lesson_number,
            "subject": s.subject,
            "room": s.room,
            "teacher": s.teacher,
            "start_time": s.start_time.strftime("%H:%M:%S") if s.start_time else "08:00:00",
            "end_time": s.end_time.strftime("%H:%M:%S") if s.end_time else "08:45:00",
        })
    return out


@router.post("/", response_model=ScheduleOut)
@router.post("", response_model=ScheduleOut, include_in_schema=False)
def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не привязаны к классу. Обратитесь к админу.")
    item = Schedule(
        class_id=membership.class_id,
        day_of_week=data.day_of_week,
        lesson_number=data.lesson_number,
        subject=data.subject,
        room=data.room,
        teacher=data.teacher,
        start_time=data.start_time,
        end_time=data.end_time
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "day_of_week": item.day_of_week,
        "lesson_number": item.lesson_number,
        "subject": item.subject,
        "room": item.room,
        "teacher": item.teacher,
        "start_time": item.start_time.strftime("%H:%M:%S") if item.start_time else "08:00:00",
        "end_time": item.end_time.strftime("%H:%M:%S") if item.end_time else "08:45:00",
    }


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(item)
    db.commit()
    return {"message": "Deleted"}
