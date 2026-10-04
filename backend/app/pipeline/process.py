"""Per-item pipeline: transcribe -> triage -> extract -> verify quotes and speakers ->
credit speakers -> tag -> dedup -> store."""

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm import client as llm
from app.llm.prompts import MAX_VIEWPOINTS
from app.models import MediaItem, MediaStatus, Viewpoint
from app.pipeline.embed import embed_texts, nearest_same_person, store_embedding
from app.pipeline.quotes import quote_in_source
from app.pipeline.speakers import resolve_speaker, speaker_verified
from app.pipeline.tags import resolve_tags
from app.pipeline.transcribe import TranscriptUnavailable, transcribe_item
from app.pipeline.transcribe.base import parse_ts

log = structlog.get_logger()

# text platforms carry their content in the feed body; below this there's nothing to mine
MIN_TEXT_CHARS = 200


def process_item(db: Session, item: MediaItem) -> list[Viewpoint]:
    """Advance an item through the pipeline. Returns newly created (non-repeat) viewpoints.

    Commits after each stage. SQLite has a single writer lock, held from a transaction's first
    write until commit, so no write may be pending while we wait on transcription or LLM calls.
    """
    s = get_settings()
    db.commit()
    person = item.source.person
    usage = dict(item.llm_usage or {})

    if item.status == MediaStatus.new:
        try:
            t = transcribe_item(item)
        except TranscriptUnavailable as e:
            return _finish(item, MediaStatus.skipped, f"no transcript: {e}")
        item.transcript = t.text
        if t.usage:
            usage["transcribe"] = t.usage
        item.status = MediaStatus.fetched
        db.commit()

    text = item.transcript or ""
    if len(text) < MIN_TEXT_CHARS:
        return _finish(item, MediaStatus.skipped, "too short")
    if len(text) > s.max_input_chars:
        return _finish(item, MediaStatus.failed, f"input too large ({len(text)} chars)")

    if item.status == MediaStatus.fetched:
        verdict, usage["triage"] = llm.triage(person.name, item.title, text)
        item.llm_usage = usage
        if not verdict.has_viewpoints:
            return _finish(item, MediaStatus.skipped, f"triage: {verdict.reason}")
        item.status = MediaStatus.triaged
        db.commit()

    result, usage["extract"] = llm.extract(
        person.name, person.bio, item.platform.value, item.title, text
    )
    item.llm_usage = usage

    verified = [
        v
        for v in result.viewpoints
        if quote_in_source(v.verbatim_quote, text, s.quote_match_threshold)
        and speaker_verified(v.speaker, person, text, item.title)
    ]
    dropped = len(result.viewpoints) - len(verified)
    if dropped:
        log.warning("viewpoints_unverified", item=item.id, dropped=dropped)
    verified = verified[:MAX_VIEWPOINTS]  # the model ranks by value; enforce the cap regardless

    vectors = embed_texts([v.claim for v in verified]) or [None] * len(verified)
    created = []
    for ev, vec in zip(verified, vectors, strict=True):
        speaker = resolve_speaker(db, ev.speaker, ev.speaker_bio, person, ev.domains)
        vp = Viewpoint(
            media_item_id=item.id,
            person_id=speaker.id,
            claim=ev.claim,
            summary=ev.summary,
            quote=ev.verbatim_quote,
            quote_translation=ev.quote_translation,
            quote_timestamp=parse_ts(ev.timestamp) if ev.timestamp else None,
            stance=ev.stance,
            confidence=max(0.0, min(1.0, ev.confidence)),
            quote_verified=True,
            tags=resolve_tags(
                db, ev.domains, ev.topics, ev.entities, [(t.symbol, t.company) for t in ev.tickers]
            ),
        )
        if vec is not None:
            neighbors = nearest_same_person(db, speaker.id, vec, k=1)
            if neighbors and neighbors[0][1] >= s.dedup_similarity:
                vp.repeat_of_id = neighbors[0][0]
                vp.novelty_score = 1.0 - neighbors[0][1]
            elif neighbors:
                vp.novelty_score = 1.0 - neighbors[0][1]
        db.add(vp)
        db.flush()
        if vec is not None:
            store_embedding(db, vp.id, speaker.id, vec)
        if vp.repeat_of_id is None:
            created.append(vp)

    _finish(item, MediaStatus.extracted, None)
    log.info("extracted", item=item.id, viewpoints=len(verified), new=len(created))
    return created


def _finish(item: MediaItem, status: MediaStatus, note: str | None) -> list[Viewpoint]:
    item.status = status
    item.error = note
    return []
