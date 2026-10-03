import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.prompts import DOMAINS
from app.models import Tag, TagKind


def slugify(name: str) -> str:
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if ascii_slug:
        return ascii_slug
    # names with no Latin letters or digits (e.g. "徐梦迪") keep their own characters
    return re.sub(r"[\W_]+", "-", name.lower()).strip("-")


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
    ticker_slugs = {re.sub(r"[^A-Z0-9.]", "", t.upper()).lower() for t in tickers}
    for e in entities:
        # "QQQ" as both entity and ticker would show twice on the card
        if (slug := slugify(e)) and slug not in ticker_slugs:
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
