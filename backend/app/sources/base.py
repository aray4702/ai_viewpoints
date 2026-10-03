from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import struct_time

import httpx

from app.models import Platform, Source

USER_AGENT = "Mozilla/5.0 (compatible; TheirTake/0.1)"


@dataclass
class MediaItemDraft:
    external_id: str
    url: str
    title: str | None = None
    published_at: datetime | None = None
    raw_text: str | None = None
    extra: dict = field(default_factory=dict)  # adapter-specific (e.g. audio_url)


@dataclass
class FetchResult:
    items: list[MediaItemDraft]
    cursor: str | None = None  # stored back on Source for the next poll


class SourceAdapter(ABC):
    platform: Platform

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )

    @abstractmethod
    def fetch_new(self, source: Source) -> FetchResult:
        """Return items newer than source.cursor (adapters may return already-seen items;
        the poller dedups on (platform, external_id))."""


def struct_to_dt(t: struct_time | None) -> datetime | None:
    return datetime(*t[:6], tzinfo=UTC) if t else None
