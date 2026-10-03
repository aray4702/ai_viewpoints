"""Credit each viewpoint to its speaker: the tracked person, a known person, or a new guest."""

import re

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm.prompts import DOMAINS
from app.models import Person
from app.pipeline.tags import slugify

log = structlog.get_logger()


def name_in_source(name: str, *texts: str | None) -> bool:
    """Guard against invented speakers: the surname must appear in the content or title."""
    parts = re.findall(r"[^\W\d_]+", name)
    if not parts:
        return False
    surname = parts[-1].lower()
    haystack = " ".join(t for t in texts if t).lower()
    return re.search(rf"\b{re.escape(surname)}\b", haystack) is not None


def is_tracked(speaker: str, tracked: Person) -> bool:
    return slugify(speaker) in (tracked.slug, slugify(tracked.name))


def speaker_verified(speaker: str, tracked: Person, *texts: str | None) -> bool:
    """The tracked person is a given (their own blog rarely names them); anyone else must be
    named in the content."""
    return is_tracked(speaker, tracked) or name_in_source(speaker, *texts)


def _unique_slug(db: Session, base: str) -> str:
    slug, n = base, 2
    while db.scalar(select(Person.id).where(Person.slug == slug)) is not None:
        slug, n = f"{base}-{n}", n + 1
    return slug


def resolve_speaker(
    db: Session,
    speaker: str,
    bio: str | None,
    tracked: Person,
    domains: list[str],
) -> Person:
    if is_tracked(speaker, tracked):
        return tracked
    name = " ".join(speaker.split())
    key = slugify(name)
    existing = db.scalar(
        select(Person).where((Person.slug == key) | (func.lower(Person.name) == name.lower()))
    )
    if existing is not None:
        return existing
    person = Person(
        name=name,
        slug=_unique_slug(db, key),
        bio=bio,
        domains=sorted({slugify(d) for d in domains} & set(DOMAINS)),
        auto_added=True,
    )
    db.add(person)
    db.flush()
    log.info("guest_added", person=person.slug, via=tracked.slug)
    return person
