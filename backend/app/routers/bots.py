from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bot, Document, User
from ..schemas import BotCreate, BotOut, BotUpdate
from ..security import get_current_user
from .deps import owned_bot

router = APIRouter(prefix="/api/bots", tags=["bots"])


def _out(bot: Bot, n_docs: int) -> BotOut:
    out = BotOut.model_validate(bot)
    out.n_documents = n_docs
    return out


@router.get("", response_model=list[BotOut])
def list_bots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Bot, func.count(Document.id))
        .outerjoin(Document, Document.bot_id == Bot.id)
        .where(Bot.owner_id == user.id).group_by(Bot.id).order_by(Bot.created_at.desc())
    ).all()
    return [_out(b, n) for b, n in rows]


@router.post("", response_model=BotOut, status_code=201)
def create_bot(body: BotCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = Bot(owner_id=user.id, name=body.name.strip())
    db.add(bot)
    db.commit()
    return _out(bot, 0)


@router.get("/{bot_id}", response_model=BotOut)
def get_bot(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count(Document.id)).where(Document.bot_id == bot.id))
    return _out(bot, n or 0)


@router.patch("/{bot_id}", response_model=BotOut)
def update_bot(body: BotUpdate, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(bot, k, v)
    db.commit()
    return get_bot(bot, db)


@router.delete("/{bot_id}", status_code=204)
def delete_bot(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    db.delete(bot)
    db.commit()
