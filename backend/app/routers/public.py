"""Public endpoints used by the embeddable widget.

Security model: `public_id` is public (it's in the page source), so the control that matters
is the per-bot **Origin allow-list**. Requests whose Origin isn't allowed get no CORS headers
(the browser blocks the response) and a 403. Phase 2 adds Redis token-bucket rate limits,
since non-browser clients can forge Origin.
"""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bot
from ..schemas import PublicChatRequest
from ..services.chat import chat_stream
from .chat import SSE_HEADERS

router = APIRouter(prefix="/public", tags=["public"])


def origin_host(origin: str | None) -> str | None:
    if not origin or origin == "null":
        return None
    try:
        parts = urlsplit(origin)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return parts.hostname.lower()


def host_allowed(host: str | None, allowed: list[str]) -> bool:
    if not host:
        return False
    for rule in allowed:
        rule = rule.lower()
        if rule.startswith("*."):
            if host.endswith(rule[1:]) and host != rule[2:]:
                return True
        elif host == rule:
            return True
    return False


def cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def request_origin(request: Request) -> str | None:
    """Browsers omit Origin on same-origin GETs, so fall back to the Referer's origin."""
    origin = request.headers.get("origin")
    if origin:
        return origin
    ref = request.headers.get("referer")
    if ref:
        p = urlsplit(ref)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    return None


def allowed_bot(public_id: str, request: Request, db: Session = Depends(get_db)) -> Bot:
    bot = db.scalar(select(Bot).where(Bot.public_id == public_id))
    if not bot:
        raise HTTPException(404, "bot not found")
    if not host_allowed(origin_host(request_origin(request)), bot.allowed_domains or []):
        raise HTTPException(403, "this website is not allowed to use this bot")
    return bot


@router.options("/bots/{public_id}/{rest:path}")
@router.options("/bots/{public_id}")
def preflight(public_id: str, request: Request, db: Session = Depends(get_db)):
    origin = request.headers.get("origin", "")
    bot = db.scalar(select(Bot).where(Bot.public_id == public_id))
    if not bot or not host_allowed(origin_host(origin), bot.allowed_domains or []):
        return Response(status_code=403)
    return Response(status_code=204, headers=cors_headers(origin))


@router.get("/bots/{public_id}")
def bot_info(request: Request, bot: Bot = Depends(allowed_bot)):
    return JSONResponse({"name": bot.name, "greeting": bot.greeting},
                        headers=cors_headers(request_origin(request)))


@router.post("/bots/{public_id}/chat")
def widget_chat(body: PublicChatRequest, request: Request, bot: Bot = Depends(allowed_bot)):
    headers = {**SSE_HEADERS, **cors_headers(request_origin(request))}
    # Widget visitors can't pick providers/models: always the bot's own settings.
    return StreamingResponse(chat_stream(bot.id, body.message, body.history),
                             media_type="text/event-stream", headers=headers)
