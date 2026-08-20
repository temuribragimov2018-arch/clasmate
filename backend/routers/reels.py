from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from backend.database import get_db
from backend.models.user import User
from backend.models.reels import Reel, ReelLike, ReelComment, ReelView, Follow, CoinLedger
from backend.utils.security import get_current_active_user

router = APIRouter(prefix="/api/reels", tags=["reels"])

GIFTS = [
    {"id": "rose", "name": "Роза", "emoji": "🌹", "cost": 10},
    {"id": "heart", "name": "Сердце", "emoji": "❤️", "cost": 25},
    {"id": "star", "name": "Звезда", "emoji": "⭐", "cost": 50},
    {"id": "fire", "name": "Огонь", "emoji": "🔥", "cost": 100},
    {"id": "crown", "name": "Корона", "emoji": "👑", "cost": 250},
    {"id": "diamond", "name": "Алмаз", "emoji": "💎", "cost": 500},
]


class ReelCreate(BaseModel):
    media_url: str
    media_type: str = "image"
    caption: str = ""


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


def _role(u: User) -> str:
    return (u.role.value if hasattr(u.role, "value") else str(u.role or "")).lower()


def _user_mini(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "avatar_url": u.avatar_url,
        "is_pro": bool(u.is_pro),
        "followers_count": u.followers_count or 0,
        "following_count": u.following_count or 0,
        "posts_count": u.posts_count or 0,
        "monetization_enabled": bool(u.monetization_enabled) or (u.followers_count or 0) >= 1000,
    }


def _reel_out(r: Reel, me: User, db: Session) -> dict:
    liked = db.query(ReelLike).filter(ReelLike.reel_id == r.id, ReelLike.user_id == me.id).first() is not None
    author = db.query(User).filter(User.id == r.user_id).first()
    following = False
    if author and author.id != me.id:
        following = db.query(Follow).filter(Follow.follower_id == me.id, Follow.following_id == author.id).first() is not None
    return {
        "id": r.id,
        "media_url": r.media_url,
        "media_type": r.media_type,
        "caption": r.caption or "",
        "likes_count": r.likes_count or 0,
        "comments_count": r.comments_count or 0,
        "views_count": r.views_count or 0,
        "shares_count": r.shares_count or 0,
        "created_at": r.created_at,
        "liked_by_me": liked,
        "author": _user_mini(author) if author else None,
        "following_author": following,
    }


@router.get("/")
def feed(
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if _role(current_user) == "starosta":
        raise HTTPException(403, "У аккаунта старосты нет доступа к Reels")
    q = db.query(Reel).filter(Reel.is_active == True).order_by(desc(Reel.created_at))
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    # if exhausted, loop from start
    if not items and total > 0 and offset > 0:
        items = q.offset(0).limit(limit).all()
        offset = 0
    return {
        "items": [_reel_out(r, current_user, db) for r in items],
        "offset": offset,
        "total": total,
        "exhausted": offset + limit >= total and total > 0,
    }


@router.post("/")
def create_reel(
    data: ReelCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    role = _role(current_user)
    if role in ("admin", "starosta"):
        raise HTTPException(403, "Админ и староста не публикуют Reels")
    reel = Reel(
        user_id=current_user.id,
        media_url=data.media_url,
        media_type=data.media_type if data.media_type in ("image", "video") else "image",
        caption=(data.caption or "")[:2000],
    )
    db.add(reel)
    current_user.posts_count = (current_user.posts_count or 0) + 1
    db.commit()
    db.refresh(reel)
    return _reel_out(reel, current_user, db)


@router.post("/{reel_id}/like")
def toggle_like(reel_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    reel = db.query(Reel).filter(Reel.id == reel_id, Reel.is_active == True).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    existing = db.query(ReelLike).filter(ReelLike.reel_id == reel_id, ReelLike.user_id == current_user.id).first()
    if existing:
        db.delete(existing)
        reel.likes_count = max(0, (reel.likes_count or 0) - 1)
        liked = False
    else:
        db.add(ReelLike(reel_id=reel_id, user_id=current_user.id))
        reel.likes_count = (reel.likes_count or 0) + 1
        liked = True
        # admin crown comment
        if _role(current_user) == "admin":
            db.add(ReelComment(
                reel_id=reel_id, user_id=current_user.id,
                text="👑 Администратор поставил лайк этой публикации",
                is_gift=False,
            ))
            reel.comments_count = (reel.comments_count or 0) + 1
    db.commit()
    return {"liked": liked, "likes_count": reel.likes_count}


@router.post("/{reel_id}/view")
def add_view(reel_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    if reel.user_id == current_user.id:
        return {"views_count": reel.views_count or 0}
    existing = db.query(ReelView).filter(ReelView.reel_id == reel_id, ReelView.user_id == current_user.id).first()
    if not existing:
        db.add(ReelView(reel_id=reel_id, user_id=current_user.id))
        reel.views_count = (reel.views_count or 0) + 1
        db.commit()
    return {"views_count": reel.views_count or 0}


@router.post("/{reel_id}/share")
def share(reel_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    reel.shares_count = (reel.shares_count or 0) + 1
    db.commit()
    return {"shares_count": reel.shares_count}


@router.get("/{reel_id}/comments")
def list_comments(reel_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    rows = db.query(ReelComment).filter(ReelComment.reel_id == reel_id).order_by(ReelComment.created_at).limit(100).all()
    out = []
    for c in rows:
        u = db.query(User).filter(User.id == c.user_id).first()
        out.append({
            "id": c.id, "text": c.text, "is_gift": c.is_gift, "gift_type": c.gift_type,
            "created_at": c.created_at,
            "author": _user_mini(u) if u else None,
        })
    return out


@router.post("/{reel_id}/comments")
def add_comment(reel_id: int, data: CommentCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    reel = db.query(Reel).filter(Reel.id == reel_id, Reel.is_active == True).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    c = ReelComment(reel_id=reel_id, user_id=current_user.id, text=data.text.strip()[:500])
    db.add(c)
    reel.comments_count = (reel.comments_count or 0) + 1
    db.commit()
    db.refresh(c)
    return {"id": c.id, "text": c.text, "author": _user_mini(current_user)}


@router.get("/gifts/list")
def gifts_list(current_user: User = Depends(get_current_active_user)):
    return GIFTS


@router.post("/{reel_id}/gift")
def send_gift(reel_id: int, gift_id: str = Query(...), current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    gift = next((g for g in GIFTS if g["id"] == gift_id), None)
    if not gift:
        raise HTTPException(400, "Неизвестный подарок")
    reel = db.query(Reel).filter(Reel.id == reel_id, Reel.is_active == True).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    author = db.query(User).filter(User.id == reel.user_id).first()
    if not author:
        raise HTTPException(404, "Автор не найден")
    if not author.monetization_enabled and (author.followers_count or 0) < 1000:
        raise HTTPException(400, "У автора ещё нет монетизации (нужно 1000 подписчиков)")
    if author.id == current_user.id:
        raise HTTPException(400, "Нельзя дарить себе")
    bal = current_user.coin_balance or 0
    if bal < gift["cost"]:
        raise HTTPException(400, f"Недостаточно монет (нужно {gift['cost']}, у вас {bal})")
    current_user.coin_balance = bal - gift["cost"]
    author.coin_balance = (author.coin_balance or 0) + gift["cost"]
    db.add(CoinLedger(user_id=current_user.id, delta=-gift["cost"], reason="gift_out", ref_id=reel_id))
    db.add(CoinLedger(user_id=author.id, delta=gift["cost"], reason="gift_in", ref_id=reel_id))
    text = f"🎁 @{current_user.username} отправил подарок {gift['emoji']} {gift['name']}"
    db.add(ReelComment(reel_id=reel_id, user_id=current_user.id, text=text, is_gift=True, gift_type=gift_id))
    reel.comments_count = (reel.comments_count or 0) + 1
    db.commit()
    return {"ok": True, "balance": current_user.coin_balance, "message": text}


@router.post("/follow/{user_id}")
def toggle_follow(user_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(400, "Нельзя подписаться на себя")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    existing = db.query(Follow).filter(Follow.follower_id == current_user.id, Follow.following_id == user_id).first()
    if existing:
        db.delete(existing)
        current_user.following_count = max(0, (current_user.following_count or 0) - 1)
        target.followers_count = max(0, (target.followers_count or 0) - 1)
        following = False
    else:
        db.add(Follow(follower_id=current_user.id, following_id=user_id))
        current_user.following_count = (current_user.following_count or 0) + 1
        target.followers_count = (target.followers_count or 0) + 1
        following = True
        if (target.followers_count or 0) >= 1000:
            target.monetization_enabled = True
    db.commit()
    return {"following": following, "followers_count": target.followers_count}



@router.delete("/{reel_id}")
def delete_reel(reel_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    reel = db.query(Reel).filter(Reel.id == reel_id).first()
    if not reel:
        raise HTTPException(404, "Не найдено")
    role = _role(current_user)
    if reel.user_id != current_user.id and role != "admin":
        raise HTTPException(403, "Можно удалить только свою публикацию")
    author = db.query(User).filter(User.id == reel.user_id).first()
    if author and (author.posts_count or 0) > 0:
        author.posts_count = max(0, (author.posts_count or 0) - 1)
    db.delete(reel)
    db.commit()
    return {"ok": True, "message": "Удалено"}

@router.get("/user/{user_id}")
def user_profile(user_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "Не найден")
    posts = db.query(Reel).filter(Reel.user_id == user_id, Reel.is_active == True).order_by(desc(Reel.created_at)).limit(50).all()
    following = db.query(Follow).filter(Follow.follower_id == current_user.id, Follow.following_id == user_id).first() is not None
    return {
        "user": _user_mini(u),
        "following": following,
        "posts": [_reel_out(r, current_user, db) for r in posts],
    }
