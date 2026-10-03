from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaItem, Source
from app.sources import ADAPTERS, get_adapter

log = structlog.get_logger()

# on a source's first poll, only items this recent are queued (no mass backfill)
FIRST_POLL_DAYS = 14


def due_sources(db: Session, now: datetime | None = None) -> list[Source]:
    now = now or datetime.now(UTC)
    # platforms without an adapter yet (e.g. x) would never get last_polled_at set,
    # so they'd come due every minute forever
    sources = db.scalars(
        select(Source).where(Source.active.is_(True), Source.platform.in_(list(ADAPTERS)))
    ).all()
    return [
        s
        for s in sources
        if s.last_polled_at is None
        or _aware(s.last_polled_at) + timedelta(minutes=s.poll_interval_min) <= now
    ]


def poll_source(db: Session, source: Source) -> list[MediaItem]:
    """Fetch the source and insert unseen items. Returns the new MediaItems."""
    adapter = get_adapter(source.platform)
    if adapter is None:
        return []
    first_poll = source.last_polled_at is None
    result = adapter.fetch_new(source)
    source.last_polled_at = datetime.now(UTC)
    source.cursor = result.cursor

    cutoff = datetime.now(UTC) - timedelta(days=FIRST_POLL_DAYS)
    ids = [d.external_id for d in result.items if d.external_id]
    seen = set(
        db.scalars(
            select(MediaItem.external_id).where(
                MediaItem.platform == source.platform, MediaItem.external_id.in_(ids)
            )
        )
    )
    new = []
    for d in result.items:
        if not d.external_id or d.external_id in seen:
            continue
        if first_poll and d.published_at and d.published_at < cutoff:
            continue
        seen.add(d.external_id)
        item = MediaItem(
            source_id=source.id,
            platform=source.platform,
            external_id=d.external_id,
            url=d.url,
            title=d.title,
            published_at=d.published_at,
            raw_text=d.raw_text,
            extra=d.extra,
        )
        db.add(item)
        new.append(item)
    db.flush()
    log.info(
        "polled", source=source.id, handle=source.handle, fetched=len(result.items), new=len(new)
    )
    return new


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
