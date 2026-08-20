from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.models.class_model import ClassMember
from backend.models.poll import Poll, PollOption, PollVote
from backend.schemas.common import PollCreate, PollOut
from backend.utils.security import get_current_active_user, require_moderator_or_admin

router = APIRouter(prefix="/api/polls", tags=["polls"])


@router.get("/", response_model=List[PollOut])
@router.get("", response_model=List[PollOut], include_in_schema=False)
def list_polls(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        return []
    polls = db.query(Poll).filter(Poll.class_id == membership.class_id, Poll.is_active == True).order_by(Poll.created_at.desc()).all()
    result = []
    for p in polls:
        voted = db.query(PollVote).filter(PollVote.poll_id == p.id, PollVote.user_id == current_user.id).first() is not None
        options = [{"id": o.id, "text": o.text, "votes_count": o.votes_count} for o in p.options]
        out = PollOut(
            id=p.id, question=p.question, ends_at=p.ends_at, is_active=p.is_active,
            created_at=p.created_at, options=options, user_voted=voted
        )
        result.append(out)
    return result


@router.post("/", response_model=PollOut)
@router.post("", response_model=PollOut, include_in_schema=False)
def create_poll(
    data: PollCreate,
    current_user: User = Depends(require_moderator_or_admin),
    db: Session = Depends(get_db)
):
    membership = db.query(ClassMember).filter(ClassMember.user_id == current_user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не привязаны к классу. Обратитесь к админу.")
    poll = Poll(
        class_id=membership.class_id,
        question=data.question,
        ends_at=data.ends_at,
        created_by=current_user.id
    )
    db.add(poll)
    db.flush()
    for text in data.options:
        db.add(PollOption(poll_id=poll.id, text=text))
    db.commit()
    db.refresh(poll)
    options = [{"id": o.id, "text": o.text, "votes_count": 0} for o in poll.options]
    return PollOut(
        id=poll.id, question=poll.question, ends_at=poll.ends_at, is_active=True,
        created_at=poll.created_at, options=options, user_voted=False
    )


@router.post("/{poll_id}/vote")
def vote(
    poll_id: int,
    option_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    poll = db.query(Poll).filter(Poll.id == poll_id, Poll.is_active == True).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    existing = db.query(PollVote).filter(PollVote.poll_id == poll_id, PollVote.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already voted")
    option = db.query(PollOption).filter(PollOption.id == option_id, PollOption.poll_id == poll_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")
    vote = PollVote(poll_id=poll_id, option_id=option_id, user_id=current_user.id)
    option.votes_count += 1
    db.add(vote)
    db.commit()
    return {"message": "Voted"}
