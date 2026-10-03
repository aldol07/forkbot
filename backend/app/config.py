"""Application settings, loaded from environment / .env (see ../.env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # botforge/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://botforge:botforge@localhost:5433/botforge"
    redis_url: str = "redis://localhost:6380/0"

    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_ttl_hours: int = 24 * 7
    cookie_name: str = "bf_session"
    cookie_secure: bool = False
    frontend_origin: str = "http://localhost:3000"

    embedding_provider: str = "fastembed"  # fastembed | openai | hash
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_cache_dir: str = str(ROOT / ".cache" / "fastembed")  # not %TEMP%, which Windows cleans

    default_llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"

    max_upload_mb: int = 10
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_k: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
