"""SQLAlchemy engine/session and schema bootstrap."""
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _adopt_create_all_database(conn, insp) -> None:
    """create_all() may already have added 0002's new tables (it creates missing tables but never
    alters existing ones). Drop them if empty so migration 0002 creates them with all indexes."""
    for t in ("messages", "conversations"):
        if insp.has_table(t):
            if conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM {t})")).scalar():
                raise RuntimeError(f"pre-migration database has rows in '{t}'; migrate it by hand")
            conn.execute(text(f"DROP TABLE {t} CASCADE"))


def init_db() -> None:
    """Bring the schema to the latest Alembic revision (idempotent; runs on API startup).

    A database built by the old create_all() (tables but no alembic_version) is stamped at the
    baseline revision first, so only the newer migrations run against it.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        insp = inspect(conn)
        if insp.has_table("users") and not insp.has_table("alembic_version"):
            _adopt_create_all_database(conn, insp)
            command.stamp(cfg, "0001")
        command.upgrade(cfg, "head")
