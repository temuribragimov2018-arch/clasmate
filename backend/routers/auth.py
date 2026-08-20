from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.class_model import Class, ClassMember
from backend.models.chat import Chat, ChatMember, ChatType
from backend.schemas.user import UserRegister, Token, UserOut, PasswordChange
from backend.utils.security import (
    get_password_hash, verify_password, create_access_token,
    create_refresh_token, get_current_active_user
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    role = user.role.value if hasattr(user.role, "value") else str(user.role or "student")
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status or "",
        role=role,
        is_online=bool(user.is_online),
        last_activity=user.last_activity,
        is_pro=bool(user.is_pro),
        pro_until=user.pro_until,
        theme=user.theme or "light",
        streak=user.streak or 0,
        coin_balance=getattr(user, "coin_balance", 0) or 0,
        followers_count=getattr(user, "followers_count", 0) or 0,
        following_count=getattr(user, "following_count", 0) or 0,
        posts_count=getattr(user, "posts_count", 0) or 0,
        monetization_enabled=bool(getattr(user, "monetization_enabled", False)),
        created_at=user.created_at or datetime.utcnow(),
    )


@router.post("/register", response_model=UserOut)
def register(data: UserRegister, db: Session = Depends(get_db)):
    try:
        code = (data.invite_code or "").strip().upper()
        class_obj = db.query(Class).filter(Class.invite_code == code, Class.is_active == True).first()
        if not class_obj:
            raise HTTPException(status_code=400, detail="Неверный или неактивный код приглашения")

        username = data.username.strip().lower()
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Такой username уже занят")

        user = User(
            username=username,
            hashed_password=get_password_hash(data.password),
            display_name=data.display_name.strip(),
            email=data.email,
            role=UserRole.student.value,
            is_active=True,
        )
        db.add(user)
        db.flush()

        db.add(ClassMember(user_id=user.id, class_id=class_obj.id))

        general_chat = (
            db.query(Chat)
            .filter(Chat.class_id == class_obj.id, Chat.chat_type == "general")
            .first()
        )
        if not general_chat:
            general_chat = (
                db.query(Chat)
                .filter(Chat.class_id == class_obj.id)
                .first()
            )
        if general_chat:
            db.add(ChatMember(chat_id=general_chat.id, user_id=user.id))

        db.commit()
        db.refresh(user)
        return _user_out(user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка регистрации: {e}")


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        username = (form_data.username or "").strip().lower()
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

        user.is_online = True
        user.last_activity = datetime.utcnow()
        db.commit()

        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        return Token(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка входа: {e}")


@router.post("/logout")
def logout(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    current_user.is_online = False
    current_user.last_activity = datetime.utcnow()
    db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_active_user)):
    return _user_out(current_user)


@router.put("/password")
def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный старый пароль")
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
