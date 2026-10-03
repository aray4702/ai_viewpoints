"""Background jobs on a SQLite-backed huey queue.

Run the worker with:  uv run huey_consumer app.workers.tasks.huey -w 2 -k thread
"""

from datetime import UTC, datetime, timedelta

import anthropic
import structlog
from huey import SqliteHuey, crontab
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.models import MediaItem, MediaStatus, Source
from app.pipeline.poll import due_sources, poll_source
from app.pipeline.process import process_item

log = structlog.get_logger()
huey = SqliteHuey("viewpoints", filename=get_settings().queue_file)


@huey.periodic_task(crontab(minute="*"))
def schedule_polls() -> None:
    with session_scope() as db:
        ids = [s.id for s in due_sources(db)]
    for sid in ids:
        poll.schedule(args=(sid,), delay=0)


@huey.task(retries=2, retry_delay=60)
def poll(source_id: int) -> None:
    with session_scope() as db:
        src = db.get(Source, source_id)
        if src is None or not src.active:
            return
        new_ids = [i.id for i in poll_source(db, src)]
    for iid in new_ids:
        process.schedule(args=(iid,), delay=0)


@huey.task(retries=3, retry_delay=120)
def process(item_id: int) -> None:
    try:
        with session_scope() as db:
            item = db.get(MediaItem, item_id)
            if item is None or item.status in (MediaStatus.extracted, MediaStatus.skipped):
                return
            new_ids = [v.id for v in process_item(db, item)]
    except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError):
        raise  # transient: let huey retry
    except Exception as e:
        log.exception("process_failed", item=item_id)
        with session_scope() as db:
            if item := db.get(MediaItem, item_id):
                item.status, item.error = MediaStatus.failed, f"{type(e).__name__}: {e}"
        return
    if new_ids:
        on_viewpoints_created(new_ids)


def on_viewpoints_created(viewpoint_ids: list[int]) -> None:
    """Hook for subscription matching and delivery (phase 5)."""
    log.info("viewpoints_created", ids=viewpoint_ids)


@huey.periodic_task(crontab(minute="*/15"))
def retry_stuck() -> None:
    """Re-enqueue items left mid-pipeline (e.g. worker restarted). The age cutoff keeps this
    from double-processing items whose first run is still in flight."""
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    with session_scope() as db:
        ids = db.scalars(
            select(MediaItem.id).where(
                MediaItem.status.in_([MediaStatus.new, MediaStatus.fetched, MediaStatus.triaged]),
                MediaItem.created_at < cutoff,
            )
        ).all()
    for iid in ids:
        process.schedule(args=(iid,), delay=0)
