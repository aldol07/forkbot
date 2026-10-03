"""BotForge API entrypoint:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .config import get_settings
from .db import init_db
from .routers import auth, bots, chat, documents, public

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.jwt_secret.startswith("dev-insecure") or s.jwt_secret.startswith("change-me"):
        logging.getLogger("botforge").warning("JWT_SECRET is not set: fine for local dev only")
    init_db()
    yield


app = FastAPI(title="BotForge API", version="0.1.0", lifespan=lifespan)

for r in (auth.router, bots.router, documents.router, chat.router, public.router):
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
