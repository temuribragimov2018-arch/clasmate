import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.utils.security import get_current_active_user
from backend.config import get_settings

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
settings = get_settings()

ALLOWED = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/jpg",
    "application/pdf",
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/3gpp",
}


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED and not content_type.startswith("image/") and not content_type.startswith("video/"):
        raise HTTPException(400, "Допустимы изображения, видео и PDF")

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(400, f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "file.jpg")[1] or ".jpg"
    if len(ext) > 10:
        ext = ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(data)

    url = f"/uploads/{name}"
    return {"url": url, "filename": file.filename, "size": len(data)}


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(400, "Только изображения")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Аватар максимум 5 МБ")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "avatar.jpg")[1] or ".jpg"
    name = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(data)

    url = f"/uploads/{name}"
    current_user.avatar_url = url
    db.commit()
    return {"url": url, "message": "Аватар обновлён"}


@router.post("/media")
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Фото или видео для Reels / чата (до 50 МБ)."""
    content_type = (file.content_type or "").lower()
    if not (content_type.startswith("image/") or content_type.startswith("video/") or content_type in ALLOWED):
        raise HTTPException(400, f"Недопустимый тип файла: {content_type or 'unknown'}")

    data = await file.read()
    max_bytes = max(settings.max_upload_bytes, 50 * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(400, f"Файл больше {max_bytes // (1024*1024)} МБ")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "file.bin")[1] or (".mp4" if content_type.startswith("video") else ".jpg")
    if len(ext) > 10:
        ext = ".bin"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(data)

    url = f"/uploads/{name}"
    return {"url": url, "filename": file.filename, "size": len(data), "content_type": content_type}
