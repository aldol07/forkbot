"""Application settings, loaded from environment / .env (see ../.env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # forkbot/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://forkbot:forkbot@localhost:5433/forkbot"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_ttl_hours: int = 24 * 7
    cookie_name: str = "forkbot_session"
    cookie_secure: bool = False
    frontend_origin: str = "http://localhost:3000"

    embedding_provider: str = "gemini"  # gemini | openai | hash (tests); local fastembed is commented out
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 384             # must match chunks.embedding (migration 0001)
    embedding_api_key: str = ""          # defaults to the provider's server key (GEMINI_API_KEY / OPENAI_API_KEY)
    embedding_cache_dir: str = str(ROOT / ".cache" / "fastembed")  # only for the local models

    default_llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"

    # original uploads: "local" (dev) or "s3" (Supabase Storage / R2 / MinIO via the S3 API)
    storage_backend: str = "local"
    storage_dir: str = str(ROOT / "storage")
    s3_endpoint: str = ""  # Supabase: https://<ref>.storage.supabase.co/storage/v1/s3
    s3_region: str = "us-east-1"
    s3_bucket: str = "documents"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    max_upload_mb: int = 25
    max_docs_per_bot: int = 20
    max_storage_mb_per_user: int = 50
    chunk_size: int = 1200
    chunk_overlap: int = 200
    retrieval_k: int = 6           # max chunks sent to the LLM
    reranker: str = "none"         # none | cross-encoder (local, commented out: see services/rerank.py)
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 10    # fused candidates scored by the cross-encoder (CPU cost grows with this)
    rerank_max_chars: int = 1000
    rerank_min_score: float = -6.0  # cross-encoder gate threshold; see services/rerank.py
    similarity_min: float = 0.56   # similarity gate (no re-ranker): closest chunk's cosine must reach this (eval-calibrated)
    llm_fallback_provider: str = "gemini"
    # Users can paste their own provider keys (bot settings tab). With SERVER_LLM_KEYS=false bots only ever
    # use those, so the keys in this .env are never spent on users' chats (the setting for a public deploy).
    server_llm_keys: bool = True
    encryption_key: str = ""  # Fernet key for stored provider keys; derived from JWT_SECRET when empty  # used when the chosen provider is rate-limited (Groq free tier: 8k tokens/min)
    rewrite_model: str = "openai/gpt-oss-20b"  # follow-up → standalone query (Groq); other providers use their chat model
    api_docs: bool = False         # expose /docs and /openapi.json (handy locally, off by default)
    history_turns: int = 10        # prior messages sent to the LLM
    chat_retention_days: int = 90  # widget conversations older than this are purged


@lru_cache
def get_settings() -> Settings:
    return Settings()
