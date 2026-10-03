import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Platform(enum.StrEnum):
    youtube = "youtube"
    podcast = "podcast"
    blog = "blog"  # blogs, Substack, any RSS/Atom feed
    arxiv = "arxiv"
    reddit = "reddit"
    x = "x"


class MediaStatus(enum.StrEnum):
    new = "new"
    fetched = "fetched"
    triaged = "triaged"
    extracted = "extracted"
    skipped = "skipped"
    failed = "failed"


class TagKind(enum.StrEnum):
    domain = "domain"
    topic = "topic"
    entity = "entity"
    ticker = "ticker"


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    bio: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    # discovered as a guest on someone else's media rather than added by an admin
    auto_added: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sources: Mapped[list["Source"]] = relationship(back_populates="person")


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("platform", "handle"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    # platform-specific identifier: channel id, feed url, subreddit user, x handle, arxiv query
    handle: Mapped[str] = mapped_column(String(500))
    poll_interval_min: Mapped[int] = mapped_column(Integer, default=60)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(String(500))  # etag / since_id / last-seen marker
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    person: Mapped[Person] = relationship(back_populates="sources")


class MediaItem(Base):
    __tablename__ = "media_items"
    __table_args__ = (UniqueConstraint("platform", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    external_id: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    raw_text: Mapped[str | None] = mapped_column(Text)  # body / description from the feed
    transcript: Mapped[str | None] = mapped_column(Text)  # full text used for extraction
    status: Mapped[MediaStatus] = mapped_column(
        Enum(MediaStatus), default=MediaStatus.new, index=True
    )
    error: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # adapter-specific, e.g. audio_url
    # tokens per stage, for cost tracking; MutableDict so in-place updates are saved
    llm_usage: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[Source] = relationship()
    viewpoints: Mapped[list["Viewpoint"]] = relationship(back_populates="media_item")


viewpoint_tags = Table(
    "viewpoint_tags",
    Base.metadata,
    Column("viewpoint_id", ForeignKey("viewpoints.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("kind", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[TagKind] = mapped_column(Enum(TagKind))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), index=True)


class Viewpoint(Base):
    __tablename__ = "viewpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_item_id: Mapped[int] = mapped_column(
        ForeignKey("media_items.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    claim: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    quote_translation: Mapped[str | None] = mapped_column(Text)  # English, for non-English quotes
    quote_timestamp: Mapped[int | None] = mapped_column(Integer)  # seconds into audio/video
    stance: Mapped[str | None] = mapped_column(String(50))  # bullish/bearish/positive/negative/...
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    novelty_score: Mapped[float] = mapped_column(Float, default=1.0)
    repeat_of_id: Mapped[int | None] = mapped_column(ForeignKey("viewpoints.id"))
    quote_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    media_item: Mapped[MediaItem] = relationship(back_populates="viewpoints")
    person: Mapped[Person] = relationship()
    tags: Mapped[list[Tag]] = relationship(secondary=viewpoint_tags, lazy="selectin")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    discord_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    filter_expr: Mapped[str] = mapped_column(Text)
    filter_ast: Mapped[dict] = mapped_column(JSON)
    # {"discord_dm": bool, "email_digest": "daily"|"weekly"|None}
    channels: Mapped[dict] = mapped_column(JSON, default=dict)
    rss_token: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiscordChannelFeed(Base):
    __tablename__ = "discord_channel_feeds"
    __table_args__ = (UniqueConstraint("channel_id", "filter_expr"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(String(64))
    channel_id: Mapped[str] = mapped_column(String(64))
    filter_expr: Mapped[str] = mapped_column(Text)
    filter_ast: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Delivery(Base):
    """One row per (target, viewpoint, channel). Guarantees each viewpoint is sent once."""

    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("target", "viewpoint_id", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(100))  # "sub:12" or "chan:98765"
    viewpoint_id: Mapped[int] = mapped_column(ForeignKey("viewpoints.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30))  # discord_dm | discord_channel | email
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | sent | failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
