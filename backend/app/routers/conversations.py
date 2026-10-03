"""Chat history for bot owners: dashboard test chats and widget visitor chats."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bot, Conversation, Message
from ..schemas import ConversationDetail, ConversationOut, MessageOut
from .deps import owned_bot

router = APIRouter(prefix="/api/bots/{bot_id}/conversations", tags=["conversations"])


def _owned_conversation(cid: uuid.UUID, bot: Bot, db: Session) -> Conversation:
    conv = db.scalar(select(Conversation).where(Conversation.id == cid, Conversation.bot_id == bot.id))
    if not conv:
        raise HTTPException(404, "conversation not found")
    return conv


@router.get("", response_model=list[ConversationOut])
def list_conversations(source: str | None = Query(default=None, pattern="^(dashboard|widget)$"),
                       limit: int = Query(default=100, ge=1, le=500),
                       bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    q = (select(Conversation, func.count(Message.id))
         .outerjoin(Message, Message.conversation_id == Conversation.id)
         .where(Conversation.bot_id == bot.id)
         .group_by(Conversation.id).order_by(Conversation.last_message_at.desc()).limit(limit))
    if source:
        q = q.where(Conversation.source == source)
    out = []
    for conv, n in db.execute(q).all():
        item = ConversationOut.model_validate(conv)
        item.n_messages = n
        out.append(item)
    return out


@router.get("/{cid}", response_model=ConversationDetail)
def get_conversation(cid: uuid.UUID, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    conv = _owned_conversation(cid, bot, db)
    msgs = db.scalars(select(Message).where(Message.conversation_id == conv.id)
                      .order_by(Message.created_at, Message.id)).all()
    head = ConversationOut.model_validate(conv)
    head.n_messages = len(msgs)
    return ConversationDetail(conversation=head, messages=[MessageOut.model_validate(m) for m in msgs])


@router.delete("/{cid}", status_code=204)
def delete_conversation(cid: uuid.UUID, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    db.delete(_owned_conversation(cid, bot, db))
    db.commit()
