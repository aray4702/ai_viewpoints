import os
import tempfile

# point the app at a throwaway data dir before any app module builds the engine
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="viewpoints-test-")
for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "VOYAGE_API_KEY"):
    os.environ[k] = ""

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal, create_virtual_tables, engine
from app.models import Base, Person, Platform, Source


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        create_virtual_tables(conn, get_settings().embedding_dim)
    yield
    with engine.begin() as conn:
        for t in ("viewpoint_vec", "viewpoint_fts"):
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def person_source(db):
    p = Person(name="Andrej Karpathy", slug="karpathy", bio="AI researcher", domains=["ai"])
    db.add(p)
    db.flush()
    src = Source(person_id=p.id, platform=Platform.blog, handle="https://example.com/feed")
    db.add(src)
    db.flush()
    return p, src
