from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..llm.providers import provider_specs
from ..models import Bot, User
from ..schemas import ChatRequest
from ..security import get_current_user
from ..services.chat import chat_stream
from ..services.keys import load_user_keys
from .deps import owned_bot

router = APIRouter(tags=["chat"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/api/bots/{bot_id}/chat")
def owner_chat(body: ChatRequest, bot: Bot = Depends(owned_bot)):
    """Dashboard test chat. `provider`/`model` in the body override the bot's settings."""
    return StreamingResponse(
        chat_stream(bot.id, body.message, conversation_id=body.conversation_id, source="dashboard",
                    provider=body.provider, model=body.model),
        media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/api/providers")
def providers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    default = get_settings().default_llm_provider
    return [{"name": s.name, "configured": s.configured, "default_model": s.default_model,
             "key_source": s.key_source, "is_default": s.name == default}
            for s in provider_specs(load_user_keys(db, user.id)).values() if s.name != "mock"]
