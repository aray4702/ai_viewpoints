from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.llm.schemas import ExtractedViewpoint, ExtractionResult, TriageResult
from app.models import MediaItem, MediaStatus, Person, Platform, Source, Tag, Viewpoint
from app.pipeline import poll as poll_mod
from app.pipeline import process as process_mod
from app.pipeline.embed import nearest_same_person, store_embedding
from app.pipeline.quotes import quote_in_source
from app.pipeline.tags import resolve_tags
from app.pipeline.transcribe.base import fmt_ts, parse_ts
from app.sources.base import FetchResult, MediaItemDraft

POST = (
    "Some intro. I think the biggest bottleneck for LLM agents right now is reliability, "
    "not raw intelligence. Models can do impressive things but fail unpredictably. " * 3
)


def vp(quote, **kw):
    base = {
        "speaker": "Andrej Karpathy",
        "speaker_bio": None,
        "quote_translation": None,
        "claim": "Reliability, not intelligence, is the main bottleneck for LLM agents.",
        "summary": "s",
        "verbatim_quote": quote,
        "timestamp": None,
        "stance": "neutral",
        "confidence": 0.8,
        "domains": ["ai", "not-a-domain"],
        "topics": ["AI Agents"],
        "entities": ["OpenAI"],
        "tickers": ["nvda"],
    }
    return ExtractedViewpoint(**{**base, **kw})


@pytest.fixture
def fake_llm(monkeypatch):
    calls = {"triage": 0, "extract": 0}
    state = {"has": True, "viewpoints": []}

    def triage(person, title, txt):
        calls["triage"] += 1
        return TriageResult(has_viewpoints=state["has"], reason="r"), {"input_tokens": 1}

    def extract(person, bio, platform, title, txt):
        calls["extract"] += 1
        return ExtractionResult(viewpoints=state["viewpoints"]), {"input_tokens": 2}

    monkeypatch.setattr(process_mod.llm, "triage", triage)
    monkeypatch.setattr(process_mod.llm, "extract", extract)
    return calls, state


def make_item(db, src, raw=POST):
    item = MediaItem(
        source_id=src.id,
        platform=Platform.blog,
        external_id="x1",
        url="https://e.com/x1",
        title="Agents",
        raw_text=raw,
    )
    db.add(item)
    db.flush()
    return item


def test_quote_matching():
    src = "[01:02] Andrej Karpathy: I think the “bitter lesson” is basically right.\n[01:30] more"
    assert quote_in_source('I think the "bitter lesson" is basically right', src, 90)
    assert not quote_in_source("Scaling is over and transformers are dead", src, 90)


def test_timestamps_roundtrip():
    assert parse_ts(f"[{fmt_ts(3723)}]") == 3723
    assert parse_ts("02:03") == 123
    assert parse_ts("garbage") is None


def test_resolve_tags_normalizes_and_dedups(db):
    tags = resolve_tags(
        db, ["AI", "bogus"], ["AI Agents", "ai-agents"], ["OpenAI", "NVDA"], ["nvda", "$NVDA"]
    )
    kinds = sorted((t.kind.value, t.slug) for t in tags)
    assert kinds == [
        ("domain", "ai"),
        ("entity", "openai"),
        ("ticker", "nvda"),
        ("topic", "ai-agents"),
    ]
    resolve_tags(db, ["ai"], [], [], [])
    assert db.scalar(select(func.count()).select_from(Tag)) == 4


def test_process_item_happy_path(db, person_source, fake_llm):
    _, src = person_source
    _, state = fake_llm
    state["viewpoints"] = [
        vp("the biggest bottleneck for LLM agents right now is reliability, not raw intelligence"),
        vp("Transformers will be obsolete by 2027", claim="hallucinated"),
    ]
    item = make_item(db, src)
    db.commit()  # like the worker: the item is already saved before processing starts
    created = process_mod.process_item(db, item)

    assert item.status == MediaStatus.extracted
    assert len(created) == 1  # hallucinated quote dropped
    v = created[0]
    assert v.quote_verified and v.person_id == src.person_id
    assert {t.slug for t in v.tags} == {"ai", "ai-agents", "openai", "nvda"}
    assert set(item.llm_usage) == {"triage", "extract"}
    # survives a round trip to the database, not just the in-memory object
    db.commit()
    db.expire_all()
    assert set(db.get(MediaItem, item.id).llm_usage) == {"triage", "extract"}
    # FTS trigger indexed it
    hit = db.execute(
        text("SELECT rowid FROM viewpoint_fts WHERE viewpoint_fts MATCH 'reliability'")
    ).all()
    assert hit == [(v.id,)]


def test_process_item_triage_skip(db, person_source, fake_llm):
    _, src = person_source
    calls, state = fake_llm
    state["has"] = False
    item = make_item(db, src)
    assert process_mod.process_item(db, item) == []
    assert item.status == MediaStatus.skipped and calls["extract"] == 0


def test_process_item_too_short(db, person_source, fake_llm):
    _, src = person_source
    item = make_item(db, src, raw="new video out!")
    process_mod.process_item(db, item)
    assert item.status == MediaStatus.skipped and fake_llm[0]["triage"] == 0


def test_dedup_marks_repeats(db, person_source, fake_llm, monkeypatch):
    _, src = person_source
    _, state = fake_llm
    quote = "the biggest bottleneck for LLM agents right now is reliability"
    state["viewpoints"] = [vp(quote)]
    vec = [1.0] + [0.0] * 1023
    monkeypatch.setattr(process_mod, "embed_texts", lambda texts: [vec for _ in texts])

    first = process_mod.process_item(db, make_item(db, src))
    item2 = MediaItem(
        source_id=src.id, platform=Platform.blog, external_id="x2", url="u", raw_text=POST
    )
    db.add(item2)
    db.flush()
    second = process_mod.process_item(db, item2)

    assert len(first) == 1 and second == []
    repeat = db.scalar(select(Viewpoint).where(Viewpoint.media_item_id == item2.id))
    assert repeat.repeat_of_id == first[0].id
    assert nearest_same_person(db, src.person_id, vec)[0] == (first[0].id, pytest.approx(1.0))


def test_vector_search_filters_by_person(db, person_source):
    p, src = person_source
    item = make_item(db, src)
    v = Viewpoint(media_item_id=item.id, person_id=p.id, claim="c", summary="s", quote="q")
    db.add(v)
    db.flush()
    store_embedding(db, v.id, p.id, [0.0, 1.0] + [0.0] * 1022)
    assert nearest_same_person(db, p.id + 99, [0.0, 1.0] + [0.0] * 1022) == []


def test_poll_is_idempotent_and_limits_first_backfill(db, person_source, monkeypatch):
    _, src = person_source
    now = datetime.now(UTC)
    drafts = [
        MediaItemDraft(external_id="new", url="u1", published_at=now - timedelta(days=1)),
        MediaItemDraft(external_id="old", url="u2", published_at=now - timedelta(days=60)),
    ]

    class FakeAdapter:
        def fetch_new(self, source):
            return FetchResult(items=drafts, cursor="etag")

    monkeypatch.setattr(poll_mod, "get_adapter", lambda platform: FakeAdapter())
    first = poll_mod.poll_source(db, src)
    assert [i.external_id for i in first] == ["new"]
    assert src.cursor == "etag" and src.last_polled_at is not None
    # later polls take old items too (e.g. a late-published episode) but never duplicates
    second = poll_mod.poll_source(db, src)
    assert [i.external_id for i in second] == ["old"]
    assert poll_mod.poll_source(db, src) == []


def test_due_sources(db, person_source):
    _, src = person_source
    assert src in poll_mod.due_sources(db)
    src.last_polled_at = datetime.now(UTC)
    src.poll_interval_min = 60
    assert src not in poll_mod.due_sources(db)
    assert src in poll_mod.due_sources(db, now=datetime.now(UTC) + timedelta(hours=2))


def test_process_item_caps_viewpoints(db, person_source, fake_llm):
    _, src = person_source
    _, state = fake_llm
    quote = "the biggest bottleneck for LLM agents right now is reliability"
    state["viewpoints"] = [vp("not in the source at all, made up")] + [
        vp(quote, claim=f"claim {i}") for i in range(5)
    ]
    created = process_mod.process_item(db, make_item(db, src))
    # the bad quote is dropped first, then the cap keeps the top 3 in model order
    assert [v.claim for v in created] == ["claim 0", "claim 1", "claim 2"]


INTERVIEW = (
    "[00:00] Andrej Karpathy: Welcome back. Today I'm talking with Noam Brown from OpenAI.\n"
    "[00:30] Noam Brown: I think reward hacking gets much worse as you scale reinforcement "
    "learning, so labs need held-out evals for every new environment they ship.\n"
    "[01:00] Andrej Karpathy: Interesting. My own view is that agents need far better memory "
    "before they are useful for long tasks.\n" * 2
)


def test_guest_viewpoints_credited_to_guest(db, person_source, fake_llm):
    karpathy, src = person_source
    _, state = fake_llm
    state["viewpoints"] = [
        vp(
            "reward hacking gets much worse as you scale reinforcement learning",
            speaker="Noam Brown",
            speaker_bio="Research scientist at OpenAI",
            domains=["ai"],
            claim="guest view",
        ),
        vp("agents need far better memory before they are useful", claim="host view"),
        vp("agents need far better memory", speaker="Ilya Sutskever", claim="invented speaker"),
    ]
    created = process_mod.process_item(db, make_item(db, src, raw=INTERVIEW))

    by_claim = {v.claim: v for v in created}
    assert set(by_claim) == {"guest view", "host view"}  # unnamed-in-source speaker dropped
    assert by_claim["host view"].person_id == karpathy.id
    guest = by_claim["guest view"].person
    assert (guest.name, guest.slug, guest.auto_added) == ("Noam Brown", "noam-brown", True)
    assert guest.bio == "Research scientist at OpenAI" and guest.domains == ["ai"]


def test_guest_reuses_existing_person(db, person_source, fake_llm):
    _, src = person_source
    _, state = fake_llm
    existing = Person(name="Noam Brown", slug="noam", domains=[])
    db.add(existing)
    db.flush()
    state["viewpoints"] = [
        vp("reward hacking gets much worse", speaker="noam  brown", claim="guest view")
    ]
    [v] = process_mod.process_item(db, make_item(db, src, raw=INTERVIEW))
    assert v.person_id == existing.id
    assert db.scalar(select(func.count()).select_from(Person)) == 2


def test_no_write_lock_held_during_llm_calls(db, person_source, monkeypatch):
    """Another process must be able to write while we wait on the LLM."""
    import sqlite3

    from app.core.config import get_settings

    _, src = person_source
    item = make_item(db, src)  # leaves an uncommitted write pending, like poll_source
    db_file = get_settings().data_dir / "viewpoints.db"
    writes = []

    def other_process_writes():
        conn = sqlite3.connect(db_file, timeout=0.2)
        try:
            conn.execute("UPDATE people SET bio = bio")
            conn.commit()
            writes.append("ok")
        except sqlite3.OperationalError as e:
            writes.append(str(e))
        finally:
            conn.close()

    def triage(*_):
        other_process_writes()
        return TriageResult(has_viewpoints=True, reason="r"), {}

    def extract(*_):
        other_process_writes()
        return ExtractionResult(viewpoints=[]), {}

    monkeypatch.setattr(process_mod.llm, "triage", triage)
    monkeypatch.setattr(process_mod.llm, "extract", extract)
    process_mod.process_item(db, item)
    assert writes == ["ok", "ok"]


def test_dedup_only_compares_within_person(db, person_source):
    """A person's own earlier view must be found even when many other people said the same."""
    me, src = person_source
    other = Person(name="Other", slug="other", domains=[])
    db.add(other)
    db.flush()
    item = make_item(db, src)
    same = [1.0] + [0.0] * 1023
    for i in range(50):  # 50 identical claims from someone else
        v = Viewpoint(
            media_item_id=item.id, person_id=other.id, claim=f"c{i}", summary="s", quote="q"
        )
        db.add(v)
        db.flush()
        store_embedding(db, v.id, other.id, same)
    mine = Viewpoint(media_item_id=item.id, person_id=me.id, claim="mine", summary="s", quote="q")
    db.add(mine)
    db.flush()
    store_embedding(db, mine.id, me.id, [0.95, 0.31] + [0.0] * 1022)  # cosine ~0.95

    [(vid, sim)] = nearest_same_person(db, me.id, same, k=1)
    assert vid == mine.id and sim > 0.9
    store_embedding(db, mine.id, me.id, same)  # re-storing the same id must not fail


def test_due_sources_skips_platforms_without_adapter(db, person_source):
    p, _ = person_source
    x = Source(person_id=p.id, platform=Platform.x, handle="karpathy")
    db.add(x)
    db.flush()
    assert x not in poll_mod.due_sources(db)


class Track:
    def __init__(self, code, generated):
        self.language_code, self.is_generated = code, generated


def test_pick_track_prefers_original_language():
    from app.pipeline.transcribe.captions import pick_track

    def pick(*tracks):
        t = pick_track(list(tracks))
        return (t.language_code, t.is_generated)

    # human-made Chinese beats an auto-generated English track
    assert pick(Track("zh-Hans", False), Track("en", True)) == ("zh-Hans", False)
    # only speech recognition: use it
    assert pick(Track("zh", True)) == ("zh", True)
    # two human tracks: the one matching the spoken language (from the generated track) wins
    assert pick(Track("en", False), Track("zh-Hans", False), Track("zh", True)) == (
        "zh-Hans",
        False,
    )
    # auto-dubbed (many generated tracks, original unknown): English, then Chinese
    assert pick(Track("fr", True), Track("zh", True), Track("en", True)) == ("en", True)
    assert pick_track([]) is None


def test_chinese_quote_matching_ignores_caption_spacing():
    captions = "[00:00] 都在讲通胀， 但债市交易的 不是通胀\n[00:30] 而是 增长预期的变化"
    assert quote_in_source("都在讲通胀，但债市交易的不是通胀", captions, 90)
    assert quote_in_source("债市交易的不是通胀，而是增长预期的变化", captions, 90)
    assert not quote_in_source("美联储下个月一定会降息", captions, 90)


# the guest's name only appears mid-sentence, with no word boundary around it
CN_TALK = (
    "[00:00] 大家好，今天分享清华徐梦迪老师的演讲。\n"
    "[00:30] 我看到了Scaling Law的信号，具身智能的数据规模会在两年内增长十倍，"
    "所以现在投资仿真数据平台比投资硬件更划算。\n" * 4
)


def test_chinese_speaker_credited_with_translation(db, fake_llm):
    _, state = fake_llm
    host = Person(name="Best Partners TV (最佳拍档)", slug="best-partners", domains=["ai"])
    db.add(host)
    db.flush()
    src = Source(person_id=host.id, platform=Platform.blog, handle="https://example.com/cn")
    db.add(src)
    db.flush()
    quote = "具身智能的数据规模会在两年内增长十倍，所以现在投资仿真数据平台比投资硬件更划算"
    state["viewpoints"] = [
        vp(
            quote,
            speaker="徐梦迪",
            speaker_bio="Professor at Tsinghua University",
            quote_translation="Embodied-AI data will grow tenfold in two years...",
            claim="guest",
        ),
        vp("大家好，今天分享清华徐梦迪老师的演讲", speaker="最佳拍档", claim="host by alias"),
        vp(quote, speaker="李飞飞", claim="invented speaker"),
    ]
    created = process_mod.process_item(db, make_item(db, src, raw=CN_TALK))

    by_claim = {v.claim: v for v in created}
    assert set(by_claim) == {"guest", "host by alias"}
    guest = by_claim["guest"]
    assert (guest.person.name, guest.person.slug, guest.person.auto_added) == (
        "徐梦迪",
        "徐梦迪",
        True,
    )
    assert guest.quote_translation.startswith("Embodied-AI")
    assert by_claim["host by alias"].person_id == host.id  # not a duplicate "guest"
