from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..llm.providers import provider_specs
from ..models import Bot, User
from ..schemas import ChatRequest
from ..security import get_current_user
from ..services.chat import chat_stream
from .deps import owned_bot

router = APIRouter(tags=["chat"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/api/bots/{bot_id}/chat")
def owner_chat(body: ChatRequest, bot: Bot = Depends(owned_bot)):
    """Dashboard test chat. `provider`/`model` in the body override the bot's settings."""
    return StreamingResponse(
        chat_stream(bot.id, body.message, body.history, body.provider, body.model),
        media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/api/providers")
def providers(user: User = Depends(get_current_user)):
    from ..config import get_settings

    default = get_settings().default_llm_provider
    return [{"name": s.name, "configured": s.configured, "default_model": s.default_model,
             "is_default": s.name == default} for s in provider_specs().values()]
