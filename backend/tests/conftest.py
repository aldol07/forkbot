"""Test setup: real Postgres (pgvector), offline `hash` embeddings and `mock` LLM.

Point TEST_DATABASE_URL at a throwaway database (default: forkbot_test on the compose Postgres).
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://forkbot:forkbot@localhost:5433/forkbot_test"))
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32
os.environ["STORAGE_BACKEND"] = "local"
os.environ["RERANKER"] = "none"  # tests that need the gate install a fake reranker
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="forkbot-test-storage-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402


def _ensure_database():
    import psycopg

    url = make_url(os.environ["DATABASE_URL"])
    # every test DROPs all tables: never let that touch a hosted database (e.g. Supabase)
    if url.host not in ("localhost", "127.0.0.1", "::1", "db") and not os.environ.get("ALLOW_REMOTE_TEST_DB"):
        raise SystemExit(f"refusing to run tests against non-local database host {url.host!r}")
    admin = url.set(database="postgres", drivername="postgresql")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (url.database,)).fetchone():
            c.execute(f'CREATE DATABASE "{url.database}"')


_ensure_database()

from app.db import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS provider_keys, messages, conversations, chunks, documents, bots, users, "
                          "alembic_version CASCADE"))
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email="a@example.com", password="password123"):
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r


def sse_events(text_body: str):
    import json
    return [json.loads(f[6:]) for f in text_body.split("\n\n") if f.startswith("data: ")]


__all__ = ["Base", "signup", "sse_events"]
