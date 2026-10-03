"""Alembic environment: reuses the app's engine (and its DATABASE_URL from .env)."""
from alembic import context

from app import models  # noqa: F401  (register tables on Base.metadata)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # init_db() passes its open connection in; the alembic CLI does not.
    conn = context.config.attributes.get("connection")
    if conn is not None:
        _run(conn)
        return
    with engine.begin() as conn:
        _run(conn)


def _run(conn) -> None:
    context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline mode is not supported; run against a database")
run_migrations_online()
