"""Request/response models."""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PROVIDERS = {"groq", "openai", "gemini", "ollama", "mock"}
_HOST_RE = re.compile(r"^(\*\.)?([a-z0-9-]+\.)*[a-z0-9-]+$")


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str


def _clean_domains(v: list[str]) -> list[str]:
    out: list[str] = []
    for d in v:
        d = d.strip().lower()
        d = re.sub(r"^https?://", "", d).split("/")[0].split(":")[0]
        if not d:
            continue
        if not _HOST_RE.match(d):
            raise ValueError(f"invalid domain: {d}")
        if d not in out:
            out.append(d)
    return out[:20]


def _check_provider(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if v not in PROVIDERS:
        raise ValueError(f"provider must be one of {sorted(PROVIDERS)}")
    return v


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class BotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    greeting: str | None = Field(default=None, max_length=300)
    system_prompt: str | None = Field(default=None, max_length=4000)
    llm_provider: str | None = None
    llm_model: str | None = Field(default=None, max_length=100)
    allowed_domains: list[str] | None = None

    _p = field_validator("llm_provider")(_check_provider)

    @field_validator("allowed_domains")
    @classmethod
    def _d(cls, v):
        return None if v is None else _clean_domains(v)


class BotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    public_id: str
    greeting: str
    system_prompt: str
    llm_provider: str | None
    llm_model: str | None
    allowed_domains: list[str]
    created_at: datetime
    n_documents: int = 0


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    content_type: str | None
    size_bytes: int
    status: str
    error: str | None
    n_pages: int
    n_chunks: int
    has_file: bool
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None  # omit to start a new conversation
    provider: str | None = None  # per-request override, for testing providers
    model: str | None = Field(default=None, max_length=100)

    _p = field_validator("provider")(_check_provider)


VISITOR_ID = r"^[A-Za-z0-9_-]{8,64}$"


class PublicChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: uuid.UUID | None = None
    visitor_id: str = Field(pattern=VISITOR_ID)  # random id the widget keeps in localStorage


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    title: str
    created_at: datetime
    last_message_at: datetime
    n_messages: int = 0


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    sources: list[dict]
    provider: str | None
    model: str | None
    first_token_ms: int | None
    total_ms: int | None
    created_at: datetime


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


class PublicMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: str
    content: str
