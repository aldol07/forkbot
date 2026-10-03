"""Forkbot API entrypoint:  uvicorn app.main:app --reload"""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings
from .db import init_db
from .routers import auth, bots, chat, conversations, documents, keys, public
from .services.chat import purge_old_conversations

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("forkbot")
STATIC = Path(__file__).parent / "static"


async def retention_loop():
    """Purge old widget conversations at startup and then once a day."""
    while True:
        try:
            n = await run_in_threadpool(purge_old_conversations)
            if n:
                log.info("retention: purged %d old widget conversations", n)
        except Exception:  # noqa: BLE001: never let housekeeping take the API down
            log.exception("retention purge failed")
        await asyncio.sleep(24 * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.jwt_secret.startswith("dev-insecure") or s.jwt_secret.startswith("change-me"):
        log.warning("JWT_SECRET is not set: fine for local dev only")
    init_db()
    task = asyncio.create_task(retention_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


_docs = get_settings().api_docs  # interactive API docs are opt-in (API_DOCS=true), off in production
app = FastAPI(title="Forkbot API", version="0.1.0", lifespan=lifespan,
              docs_url="/docs" if _docs else None, redoc_url=None,
              openapi_url="/openapi.json" if _docs else None)

for r in (auth.router, bots.router, documents.router, chat.router, conversations.router, keys.router,
          public.router):
    app.include_router(r)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    # keep CORS headers on public errors so the widget can show a friendly message
    headers = dict(exc.headers or {})
    origin = request.headers.get("origin")
    if request.url.path.startswith("/public") and origin and exc.status_code != 403:
        headers.update(public.cors_headers(origin))
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if not request.url.path.startswith(("/widget.js", "/public")):
        resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/widget.js", include_in_schema=False)
def widget_js():
    return FileResponse(STATIC / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/demo", include_in_schema=False)
def demo_page():
    """A plain host page for trying the widget: /demo?bot=bot_xxx"""
    return FileResponse(STATIC / "demo.html", media_type="text/html")
