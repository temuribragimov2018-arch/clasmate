import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.file import File as FileModel
from backend.utils.security import get_current_active_user
from backend.config import get_settings

router = APIRouter(prefix="/api/files", tags=["files"])
settings = get_settings()


class FileOut(BaseModel):
    id: int
    original_name: str
    filename: str
    file_url: str
    file_type: Optional[str] = None
    category: Optional[str] = "other"
    size_bytes: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[FileOut])
def list_files(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    q = db.query(FileModel).filter(FileModel.class_id == membership.class_id)
    if category:
        q = q.filter(FileModel.category == category)
    items = q.order_by(FileModel.created_at.desc()).limit(100).all()
    return items


@router.post("/upload", response_model=FileOut)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("other"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(400, "Вы не состоите в классе")

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(400, f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ")

    allowed_cats = {"study", "documents", "photos", "other"}
    if category not in allowed_cats:
        category = "other"

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    original = file.filename or "file"
    ext = os.path.splitext(original)[1] or ""
    if len(ext) > 12:
        ext = ""
    stored = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, stored)
    with open(path, "wb") as f:
        f.write(data)

    url = f"/uploads/{stored}"
    row = FileModel(
        class_id=membership.class_id,
        uploaded_by=current_user.id,
        filename=stored,
        original_name=original[:255],
        file_url=url,
        file_type=(file.content_type or "")[:100],
        category=category,
        size_bytes=len(data),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(400, "Нет класса")
    row = db.query(FileModel).filter(
        FileModel.id == file_id, FileModel.class_id == membership.class_id
    ).first()
    if not row:
        raise HTTPException(404, "Файл не найден")
    # allow uploader or moderators
    is_mod = current_user.role in ("admin", "moderator", "starosta")
    if row.uploaded_by != current_user.id and not is_mod:
        raise HTTPException(403, "Нет прав")
    try:
        path = os.path.join(settings.UPLOAD_DIR, row.filename)
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass
    db.delete(row)
    db.commit()
    return {"message": "Удалено"}
