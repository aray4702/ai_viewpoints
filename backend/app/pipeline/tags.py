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


def _symbol(s: str) -> str:
    return re.sub(r"[^A-Z0-9.]", "", s.upper())


def _same_company(entity: str, companies: set[str]) -> bool:
    """'nvidia' matches 'nvidia' and 'nvidia-corporation'; 'amazon' matches 'amazon-com'."""
    return any(
        entity == c or c.startswith(entity + "-") or entity.startswith(c + "-") for c in companies
    )


def resolve_tags(
    db: Session,
    domains: list[str],
    topics: list[str],
    entities: list[str],
    tickers: list[tuple[str, str | None]],
) -> list[Tag]:
    """tickers are (symbol, company name) pairs."""
    wanted: dict[tuple[TagKind, str], str] = {}
    for d in domains:
        if slugify(d) in DOMAINS:  # domains are a closed set
            wanted[(TagKind.domain, slugify(d))] = slugify(d)
    for t in topics:
        if slug := slugify(t):
            wanted[(TagKind.topic, slug)] = t.strip().lower()
    # a company with a ticker would otherwise show twice ("Tesla" and "$TSLA")
    covered = {_symbol(sym).lower() for sym, _ in tickers}
    companies = {slugify(c) for _, c in tickers if c and slugify(c)}
    for e in entities:
        slug = slugify(e)
        if not slug or slug in covered or _same_company(slug, companies):
            continue
        wanted[(TagKind.entity, slug)] = e.strip()
    for sym, _ in tickers:
        if s := _symbol(sym):
            wanted[(TagKind.ticker, s.lower())] = s

    tags = []
    for (kind, slug), name in wanted.items():
        tag = db.scalar(select(Tag).where(Tag.kind == kind, Tag.slug == slug))
        if tag is None:
            tag = Tag(kind=kind, slug=slug, name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags
