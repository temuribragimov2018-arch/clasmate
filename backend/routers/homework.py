from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.homework import Homework, HomeworkUserStatus, HomeworkStatus
from backend.schemas.common import HomeworkCreate, HomeworkOut
from backend.utils.security import get_current_active_user, require_moderator_or_admin

router = APIRouter(prefix="/api/homework", tags=["homework"])


@router.get("/", response_model=List[HomeworkOut])
@router.get("", response_model=List[HomeworkOut], include_in_schema=False)
def list_homework(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    homeworks = db.query(Homework).filter(Homework.class_id == membership.class_id).order_by(Homework.due_date).all()
    result = []
    for hw in homeworks:
        status_obj = db.query(HomeworkUserStatus).filter(
            HomeworkUserStatus.homework_id == hw.id,
            HomeworkUserStatus.user_id == current_user.id
        ).first()
        status = status_obj.status.value if status_obj else HomeworkStatus.new.value
        # Auto overdue
        if status != HomeworkStatus.done.value and hw.due_date < datetime.utcnow():
            status = HomeworkStatus.overdue.value
        out = HomeworkOut.model_validate(hw)
        out.status = status
        result.append(out)
    return result


@router.post("/", response_model=HomeworkOut)
@router.post("", response_model=HomeworkOut, include_in_schema=False)
def create_homework(
    data: HomeworkCreate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не привязаны к классу. Обратитесь к админу.")
    hw = Homework(
        class_id=membership.class_id,
        subject=data.subject,
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        file_url=data.file_url,
        created_by=current_user.id
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return HomeworkOut.model_validate(hw)


@router.put("/{homework_id}/status")
def update_status(
    homework_id: int,
    status: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if status not in [s.value for s in HomeworkStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")
    status_obj = db.query(HomeworkUserStatus).filter(
        HomeworkUserStatus.homework_id == homework_id,
        HomeworkUserStatus.user_id == current_user.id
    ).first()
    if status_obj:
        status_obj.status = HomeworkStatus(status)
        status_obj.updated_at = datetime.utcnow()
    else:
        status_obj = HomeworkUserStatus(
            homework_id=homework_id,
            user_id=current_user.id,
            status=HomeworkStatus(status)
        )
        db.add(status_obj)
    db.commit()
    return {"status": status}
