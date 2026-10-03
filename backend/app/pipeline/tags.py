import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.prompts import DOMAINS
from app.models import Tag, TagKind


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def resolve_tags(
    db: Session, domains: list[str], topics: list[str], entities: list[str], tickers: list[str]
) -> list[Tag]:
    wanted: dict[tuple[TagKind, str], str] = {}
    for d in domains:
        if slugify(d) in DOMAINS:  # domains are a closed set
            wanted[(TagKind.domain, slugify(d))] = slugify(d)
    for t in topics:
        if slug := slugify(t):
            wanted[(TagKind.topic, slug)] = t.strip().lower()
    for e in entities:
        if slug := slugify(e):
            wanted[(TagKind.entity, slug)] = e.strip()
    for t in tickers:
        if sym := re.sub(r"[^A-Z0-9.]", "", t.upper()):
            wanted[(TagKind.ticker, sym.lower())] = sym

    tags = []
    for (kind, slug), name in wanted.items():
        tag = db.scalar(select(Tag).where(Tag.kind == kind, Tag.slug == slug))
        if tag is None:
            tag = Tag(kind=kind, slug=slug, name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags
