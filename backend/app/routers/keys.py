"""Bring your own key: users paste API keys for LLM providers and their bots use them.

Keys are encrypted at rest and never sent back to the browser, only their last 4 characters.
"""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import encrypt
from ..db import get_db
from ..llm.providers import BYOK_PROVIDERS, check_key
from ..models import ProviderKey, User
from ..security import get_current_user
from ..services.keys import load_user_keys

router = APIRouter(prefix="/api/keys", tags=["keys"])

PROVIDER = Path(pattern="^(" + "|".join(BYOK_PROVIDERS) + ")$")
KEY = Field(min_length=10, max_length=300, pattern=r"^\S+$")


class KeyIn(BaseModel):
    api_key: str = KEY


class KeyTestIn(BaseModel):
    api_key: str | None = Field(default=None, min_length=10, max_length=300, pattern=r"^\S+$")


def _row(db: Session, user: User, provider: str) -> ProviderKey | None:
    return db.scalar(select(ProviderKey).where(ProviderKey.owner_id == user.id, ProviderKey.provider == provider))


@router.get("")
def list_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = {r.provider: r for r in db.scalars(select(ProviderKey).where(ProviderKey.owner_id == user.id))}
    return [{"provider": p, "saved": p in rows, "last4": rows[p].last4 if p in rows else None,
             "updated_at": rows[p].updated_at if p in rows else None} for p in BYOK_PROVIDERS]


@router.put("/{provider}")
def save_key(body: KeyIn, provider: str = PROVIDER,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ok, msg = check_key(provider, body.api_key)  # never store a key that doesn't work
    if not ok:
        raise HTTPException(400, msg)
    row = _row(db, user, provider) or ProviderKey(owner_id=user.id, provider=provider)
    row.key_encrypted, row.last4 = encrypt(body.api_key), body.api_key[-4:]
    db.add(row)
    db.commit()
    return {"provider": provider, "saved": True, "last4": row.last4, "message": msg}


@router.post("/{provider}/test")
def test_key(body: KeyTestIn, provider: str = PROVIDER,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Test a pasted key without saving it, or the saved one when no key is sent."""
    key = body.api_key or load_user_keys(db, user.id).get(provider)
    if not key:
        raise HTTPException(404, f"no saved {provider} key to test")
    ok, msg = check_key(provider, key)
    return {"provider": provider, "ok": ok, "message": msg}


@router.delete("/{provider}", status_code=204)
def delete_key(provider: str = PROVIDER, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _row(db, user, provider)
    if row:
        db.delete(row)
        db.commit()
