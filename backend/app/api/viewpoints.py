import re

import sqlite_vec
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import MediaOut, PersonBrief, TagOut, ViewpointOut, ViewpointPage
from app.core.db import get_db
from app.models import (
    MediaItem,
    Person,
    Platform,
    Source,
    Tag,
    TagKind,
    Viewpoint,
    viewpoint_tags,
)
from app.pipeline.embed import embed_texts

router = APIRouter(prefix="/api", tags=["viewpoints"])

RRF_K = 60  # reciprocal rank fusion constant


def quote_url(v: Viewpoint) -> str:
    url = v.media_item.url
    if v.quote_timestamp is not None and v.media_item.platform == Platform.youtube:
        return f"{url}{'&' if '?' in url else '?'}t={v.quote_timestamp}s"
    return url


def to_out(v: Viewpoint) -> ViewpointOut:
    return ViewpointOut(
        id=v.id,
        claim=v.claim,
        summary=v.summary,
        quote=v.quote,
        quote_timestamp=v.quote_timestamp,
        quote_url=quote_url(v),
        stance=v.stance,
        confidence=v.confidence,
        novelty_score=v.novelty_score,
        created_at=v.created_at,
        person=PersonBrief.model_validate(v.person),
        via=(
            PersonBrief.model_validate(host)
            if (host := v.media_item.source.person).id != v.person_id
            else None
        ),
        media=MediaOut.model_validate(v.media_item),
        tags=[TagOut.model_validate(t) for t in v.tags],
    )


def _base_query():
    return select(Viewpoint).options(
        selectinload(Viewpoint.person),
        selectinload(Viewpoint.media_item)
        .selectinload(MediaItem.source)
        .selectinload(Source.person),
    )


def fts_query(q: str) -> str | None:
    """User text -> safe FTS5 query: each word quoted, prefix match on the last."""
    words = re.findall(r"\w+", q)
    if not words:
        return None
    return " ".join(f'"{w}"' for w in words[:-1]) + f' "{words[-1]}"*'


def fts_ids(db: Session, q: str, limit: int) -> list[int]:
    match = fts_query(q)
    if match is None:
        return []
    rows = db.execute(
        text("SELECT rowid FROM viewpoint_fts WHERE viewpoint_fts MATCH :q ORDER BY rank LIMIT :n"),
        {"q": match, "n": limit},
    )
    return [r[0] for r in rows]


def vector_ids(db: Session, q: str, limit: int) -> list[int]:
    vecs = embed_texts([q], input_type="query")
    if not vecs:
        return []
    rows = db.execute(
        text(
            "SELECT viewpoint_id FROM viewpoint_vec WHERE embedding MATCH :emb AND k = :k "
            "ORDER BY distance"
        ),
        {"emb": sqlite_vec.serialize_float32(vecs[0]), "k": limit},
    )
    return [r[0] for r in rows]


def apply_filters(stmt, person: list[str], tag: list[str], domain: list[str], repeats: bool):
    if person:
        stmt = stmt.join(Person, Viewpoint.person_id == Person.id).where(Person.slug.in_(person))
    for slug in tag:  # every listed tag must match (AND)
        stmt = stmt.where(Viewpoint.tags.any(Tag.slug == slug.lower()))
    if domain:
        stmt = stmt.where(
            Viewpoint.tags.any(
                (Tag.kind == TagKind.domain) & Tag.slug.in_([d.lower() for d in domain])
            )
        )
    if not repeats:
        stmt = stmt.where(Viewpoint.repeat_of_id.is_(None))
    return stmt


@router.get("/viewpoints", response_model=ViewpointPage)
def list_viewpoints(
    person: list[str] = Query(default=[]),
    tag: list[str] = Query(default=[]),
    domain: list[str] = Query(default=[]),
    q: str | None = None,
    include_repeats: bool = False,
    cursor: int | None = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    stmt = apply_filters(_base_query(), person, tag, domain, include_repeats)
    if q and fts_query(q):  # ignore queries with no searchable words
        stmt = stmt.where(Viewpoint.id.in_(fts_ids(db, q, 1000)))
    if cursor:
        stmt = stmt.where(Viewpoint.id < cursor)
    rows = db.scalars(stmt.order_by(Viewpoint.id.desc()).limit(limit + 1)).all()
    items = rows[:limit]
    return ViewpointPage(
        items=[to_out(v) for v in items],
        next_cursor=items[-1].id if len(rows) > limit else None,
    )


@router.get("/search", response_model=list[ViewpointOut])
def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
):
    """Hybrid search: FTS5 keyword ranks + vector ranks, fused with RRF."""
    scores: dict[int, float] = {}
    for ranked in (fts_ids(db, q, 100), vector_ids(db, q, 100)):
        for rank, vid in enumerate(ranked):
            scores[vid] = scores.get(vid, 0.0) + 1.0 / (RRF_K + rank + 1)
    top = sorted(scores, key=scores.get, reverse=True)[: limit * 2]
    if not top:
        return []
    found = {
        v.id: v
        for v in db.scalars(
            _base_query().where(Viewpoint.id.in_(top), Viewpoint.repeat_of_id.is_(None))
        )
    }
    return [to_out(found[i]) for i in top if i in found][:limit]


@router.get("/viewpoints/{viewpoint_id}", response_model=ViewpointOut)
def get_viewpoint(viewpoint_id: int, db: Session = Depends(get_db)):
    v = db.scalar(_base_query().where(Viewpoint.id == viewpoint_id))
    if v is None:
        raise HTTPException(404, "not found")
    return to_out(v)


@router.get("/tags", response_model=list[TagOut])
def list_tags(
    q: str | None = None,
    kind: TagKind | None = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """For filter autocomplete; most-used tags first."""
    stmt = (
        select(Tag)
        .join(viewpoint_tags, viewpoint_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count().desc())
        .limit(limit)
    )
    if q:
        stmt = stmt.where(Tag.slug.like(f"{q.lower()}%") | Tag.name.ilike(f"%{q}%"))
    if kind:
        stmt = stmt.where(Tag.kind == kind)
    return [TagOut.model_validate(t) for t in db.scalars(stmt)]
