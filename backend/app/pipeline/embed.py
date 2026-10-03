"""Claim embeddings (Voyage) stored in the sqlite-vec table, used for dedup and semantic search."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import sqlite_vec
from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def _client():
    import voyageai

    key = get_settings().voyage_api_key
    return voyageai.Client(api_key=key) if key else None


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]] | None:
    """Returns None when embeddings aren't configured; callers then skip dedup/vector search."""
    client = _client()
    if client is None or not texts:
        return None
    return client.embed(
        texts, model=get_settings().embedding_model, input_type=input_type
    ).embeddings


def store_embedding(db: Session, viewpoint_id: int, person_id: int, vec: list[float]) -> None:
    # vec0 has no upsert: INSERT OR REPLACE fails on an existing primary key
    db.execute(text("DELETE FROM viewpoint_vec WHERE viewpoint_id = :id"), {"id": viewpoint_id})
    db.execute(
        text(
            "INSERT INTO viewpoint_vec(viewpoint_id, person_id, embedding) VALUES (:id, :pid, :emb)"
        ),
        {"id": viewpoint_id, "pid": person_id, "emb": sqlite_vec.serialize_float32(vec)},
    )


def nearest_same_person(
    db: Session, person_id: int, vec: list[float], k: int = 5
) -> list[tuple[int, float]]:
    """(viewpoint_id, cosine_similarity) for this person's recent viewpoints, most similar first."""
    s = get_settings()
    since = datetime.now(UTC) - timedelta(days=s.dedup_window_days)
    rows = db.execute(
        text(
            "SELECT v.id, n.distance FROM ("
            "  SELECT viewpoint_id, distance FROM viewpoint_vec"
            "  WHERE embedding MATCH :emb AND k = :k AND person_id = :pid"
            ") n JOIN viewpoints v ON v.id = n.viewpoint_id "
            "WHERE v.created_at >= :since AND v.repeat_of_id IS NULL "
            "ORDER BY n.distance"
        ).bindparams(bindparam("since", type_=DateTime(timezone=True))),
        # the KNN only sees this person's rows; over-fetch for the age/repeat filter after it
        {"emb": sqlite_vec.serialize_float32(vec), "k": k * 20, "pid": person_id, "since": since},
    ).all()
    return [(vid, 1.0 - dist) for vid, dist in rows[:k]]
