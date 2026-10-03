"""SQLite engine with WAL, sqlite-vec, and FTS5 support."""

from collections.abc import Iterator
from contextlib import contextmanager

import sqlite_vec
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return engine


engine = make_engine(get_settings().db_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s


def vec_table_def(dim: int) -> str:
    # partitioned by person so nearest-neighbour lookups for dedup only scan that person's rows
    return (
        "vec0(viewpoint_id INTEGER PRIMARY KEY, person_id INTEGER partition key, "
        f"embedding float[{dim}] distance_metric=cosine)"
    )


def create_virtual_tables(conn, dim: int) -> None:
    """sqlite-vec and FTS5 tables aren't expressible as ORM models; create them here."""
    conn.execute(
        text(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS viewpoint_vec USING {vec_table_def(dim)}"
        )
    )
    conn.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS viewpoint_fts USING fts5("
            "claim, summary, quote, content='viewpoints', content_rowid='id')"
        )
    )
    # keep FTS in sync with viewpoints
    conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS viewpoints_ai AFTER INSERT ON viewpoints BEGIN "
            "INSERT INTO viewpoint_fts(rowid, claim, summary, quote) "
            "VALUES (new.id, new.claim, new.summary, new.quote); END"
        )
    )
    conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS viewpoints_ad AFTER DELETE ON viewpoints BEGIN "
            "INSERT INTO viewpoint_fts(viewpoint_fts, rowid, claim, summary, quote) "
            "VALUES ('delete', old.id, old.claim, old.summary, old.quote); END"
        )
    )
    conn.execute(
        text(
            "CREATE TRIGGER IF NOT EXISTS viewpoints_au AFTER UPDATE ON viewpoints BEGIN "
            "INSERT INTO viewpoint_fts(viewpoint_fts, rowid, claim, summary, quote) "
            "VALUES ('delete', old.id, old.claim, old.summary, old.quote); "
            "INSERT INTO viewpoint_fts(rowid, claim, summary, quote) "
            "VALUES (new.id, new.claim, new.summary, new.quote); END"
        )
    )
