import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bot, User
from ..security import get_current_user


def owned_bot(bot_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Bot:
    """Tenant scoping: a bot is only visible to its owner (404, not 403, to avoid leaking existence)."""
    bot = db.scalar(select(Bot).where(Bot.id == bot_id, Bot.owner_id == user.id))
    if not bot:
        raise HTTPException(404, "bot not found")
    return bot
