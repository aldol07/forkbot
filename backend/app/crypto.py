"""Encryption at rest for secrets users paste in (their LLM provider API keys).

Fernet (AES-128-CBC + HMAC). The key comes from ENCRYPTION_KEY, or is derived from JWT_SECRET when
that isn't set. Changing whichever one is in use makes stored provider keys unreadable: users then
have to paste them again (the app treats an undecryptable key as missing).
"""
import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    if s.encryption_key:
        return Fernet(s.encryption_key.encode())
    digest = hashlib.sha256(b"provider-keys:" + s.jwt_secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
