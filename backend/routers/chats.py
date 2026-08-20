from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.chat import Chat, ChatMember, Message, Reaction, ChatType
from backend.schemas.chat import MessageCreate, MessageUpdate, MessageOut, ChatOut, ChatCreate, ReactionCreate
from backend.utils.security import get_current_active_user, decode_token

router = APIRouter(prefix="/api/chats", tags=["chats"])

# Simple in-memory connection manager for WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}  # user_id -> websockets

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def broadcast_to_chat(self, chat_id: int, message: dict, db: Session, exclude_user: int = None):
        members = db.query(ChatMember).filter(ChatMember.chat_id == chat_id).all()
        for m in members:
            if exclude_user and m.user_id == exclude_user:
                continue
            await self.send_to_user(m.user_id, message)


manager = ConnectionManager()


def _message_out(msg, sender_data=None) -> MessageOut:
    """Safe MessageOut — avoids Pydantic errors on ORM relations."""
    if sender_data is None and getattr(msg, "sender", None) is not None:
        s = msg.sender
        sender_data = {
            "id": s.id,
            "username": s.username,
            "display_name": s.display_name,
            "avatar_url": getattr(s, "avatar_url", None),
        }
    reactions = []
    try:
        reactions = [{"emoji": r.emoji, "user_id": r.user_id} for r in (msg.reactions or [])]
    except Exception:
        pass
    return MessageOut(
        id=msg.id,
        chat_id=msg.chat_id,
        sender_id=msg.sender_id,
        content=msg.content,
        reply_to_id=msg.reply_to_id,
        is_edited=bool(msg.is_edited) if msg.is_edited is not None else False,
        is_deleted=bool(msg.is_deleted) if msg.is_deleted is not None else False,
        is_pinned=bool(msg.is_pinned) if msg.is_pinned is not None else False,
        file_url=msg.file_url,
        file_name=msg.file_name,
        file_type=msg.file_type,
        created_at=msg.created_at,
        updated_at=msg.updated_at or msg.created_at,
        sender=sender_data,
        reactions=reactions,
    )



@router.get("/", response_model=List[ChatOut])
def list_chats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    memberships = db.query(ChatMember).filter(ChatMember.user_id == current_user.id).all()
    result = []
    role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role or "")).lower()
    for m in memberships:
        chat = m.chat
        if not chat or not chat.is_active:
            continue
        ctype = str(getattr(chat.chat_type, "value", chat.chat_type) or "")
        # Admin does not see class general chats (only staff chat)
        if role == "admin" and ctype == "general":
            continue
        last_msg = (
            db.query(Message)
            .filter(Message.chat_id == chat.id, Message.is_deleted == False)
            .order_by(desc(Message.created_at))
            .first()
        )
        unread = 0
        if m.last_read_message_id:
            unread = db.query(Message).filter(
                Message.chat_id == chat.id,
                Message.id > m.last_read_message_id,
                Message.is_deleted == False,
                Message.sender_id != current_user.id
            ).count()
        else:
            unread = db.query(Message).filter(
                Message.chat_id == chat.id,
                Message.is_deleted == False,
                Message.sender_id != current_user.id
            ).count()

        result.append(ChatOut(
            id=chat.id,
            name=chat.name or ("Общий чат" if str(getattr(chat.chat_type, "value", chat.chat_type)) == "general" else "Чат"),
            chat_type=(chat.chat_type.value if hasattr(chat.chat_type, "value") else str(chat.chat_type)),
            class_id=chat.class_id,
            created_at=chat.created_at,
            unread_count=unread,
            last_message=_message_out(last_msg) if last_msg else None
        ))
    return result


@router.post("/", response_model=ChatOut)
def create_group_chat(
    data: ChatCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    chat = Chat(
        name=data.name,
        chat_type="group",
        class_id=membership.class_id if membership else None,
        created_by=current_user.id
    )
    db.add(chat)
    db.flush()
    # Add creator
    db.add(ChatMember(chat_id=chat.id, user_id=current_user.id))
    for uid in data.member_ids:
        if uid != current_user.id:
            db.add(ChatMember(chat_id=chat.id, user_id=uid))
    db.commit()
    db.refresh(chat)
    return ChatOut(
        id=chat.id, name=chat.name, chat_type=(chat.chat_type.value if hasattr(chat.chat_type, "value") else str(chat.chat_type)),
        class_id=chat.class_id, created_at=chat.created_at
    )


@router.get("/{chat_id}/messages", response_model=List[MessageOut])
def get_messages(
    chat_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    member = db.query(ChatMember).filter(
        ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this chat")

    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat_id, Message.is_deleted == False)
        .order_by(desc(Message.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    messages.reverse()

    result = []
    for msg in messages:
        result.append(_message_out(msg))
    return result


@router.post("/{chat_id}/messages", response_model=MessageOut)
async def send_message(
    chat_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    member = db.query(ChatMember).filter(
        ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this chat")

    if not (data.content and str(data.content).strip()) and not data.file_url:
        raise HTTPException(status_code=400, detail="Нужен текст или файл")

    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=data.content,
        reply_to_id=data.reply_to_id,
        file_url=data.file_url,
        file_name=data.file_name,
        file_type=data.file_type
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    out = _message_out(msg, sender_data={
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
    })

    await manager.broadcast_to_chat(chat_id, {
        "type": "new_message",
        "message": out.model_dump(mode="json")
    }, db, exclude_user=current_user.id)

    return out


@router.put("/messages/{message_id}", response_model=MessageOut)
def edit_message(
    message_id: int,
    data: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg or msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit this message")
    msg.content = data.content
    msg.is_edited = True
    msg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return _message_out(msg)


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id and current_user.role.value not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Cannot delete this message")
    msg.is_deleted = True
    db.commit()
    return {"message": "Deleted"}


@router.post("/messages/{message_id}/reactions")
def add_reaction(
    message_id: int,
    data: ReactionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    existing = db.query(Reaction).filter(
        Reaction.message_id == message_id, Reaction.user_id == current_user.id, Reaction.emoji == data.emoji
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "Reaction removed"}
    reaction = Reaction(message_id=message_id, user_id=current_user.id, emoji=data.emoji)
    db.add(reaction)
    db.commit()
    return {"message": "Reaction added"}


@router.post("/messages/{message_id}/pin")
def pin_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if current_user.role.value not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Only moderators can pin")
    msg.is_pinned = not msg.is_pinned
    db.commit()
    return {"is_pinned": msg.is_pinned}




@router.post("/{chat_id}/read")
def mark_read(chat_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    membership = db.query(ChatMember).filter(ChatMember.chat_id == chat_id, ChatMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member")
    last = (
        db.query(Message)
        .filter(Message.chat_id == chat_id, Message.is_deleted == False)
        .order_by(desc(Message.created_at))
        .first()
    )
    if last:
        membership.last_read_message_id = last.id
        db.commit()
    return {"ok": True}

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id)
    user.is_online = True
    user.last_activity = datetime.utcnow()
    db.commit()

    try:
        while True:
            data = await websocket.receive_json()
            # Handle typing indicator etc.
            if data.get("type") == "typing":
                chat_id = data.get("chat_id")
                if chat_id:
                    await manager.broadcast_to_chat(chat_id, {
                        "type": "typing",
                        "user_id": user_id,
                        "username": user.username,
                        "chat_id": chat_id
                    }, db, exclude_user=user_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        user.is_online = False
        user.last_activity = datetime.utcnow()
        db.commit()
