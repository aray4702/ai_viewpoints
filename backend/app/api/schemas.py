from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import Platform, TagKind


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: TagKind
    slug: str
    name: str


class PersonBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    avatar_url: str | None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform: Platform
    handle: str
    poll_interval_min: int
    last_polled_at: datetime | None
    active: bool


class PersonOut(PersonBrief):
    bio: str | None
    domains: list[str]
    auto_added: bool
    viewpoint_count: int = 0


class PersonDetail(PersonOut):
    sources: list[SourceOut]


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform: Platform
    url: str
    title: str | None
    published_at: datetime | None


class ViewpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    claim: str
    summary: str
    quote: str
    quote_translation: str | None  # English, when the quote isn't
    quote_timestamp: int | None
    quote_url: str  # source link, deep-linked to the timestamp when possible
    stance: str | None
    confidence: float
    novelty_score: float
    created_at: datetime
    person: PersonBrief
    via: PersonBrief | None  # whose channel/feed it came from, when that's not the speaker
    media: MediaOut
    tags: list[TagOut]


class ViewpointPage(BaseModel):
    items: list[ViewpointOut]
    next_cursor: int | None


class UserOut(BaseModel):
    id: int
    email: str | None
    discord_id: str | None
    is_admin: bool


class PersonIn(BaseModel):
    name: str
    slug: str
    bio: str | None = None
    domains: list[str] = []
    avatar_url: str | None = None


class SourceIn(BaseModel):
    platform: Platform
    handle: str
    poll_interval_min: int = 60


class SourcePatch(BaseModel):
    active: bool | None = None
    poll_interval_min: int | None = None
