"""RSS/Atom based adapters: blogs/Substack, podcasts, YouTube channel feeds, arXiv."""

import re
from typing import ClassVar
from urllib.parse import quote_plus

import feedparser

from app.models import Platform, Source
from app.sources.base import FetchResult, MediaItemDraft, SourceAdapter, struct_to_dt
from app.sources.html import html_to_text


class FeedAdapter(SourceAdapter):
    """Generic feed reader. Subclasses override feed_url() and to_draft()."""

    def feed_url(self, source: Source) -> str:
        return source.handle

    def fetch_new(self, source: Source) -> FetchResult:
        headers = {"If-None-Match": source.cursor} if source.cursor else {}
        resp = self.client.get(self.feed_url(source), headers=headers)
        if resp.status_code == 304:
            return FetchResult(items=[], cursor=source.cursor)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        items = [d for e in parsed.entries if (d := self.to_draft(e)) is not None]
        return FetchResult(items=items, cursor=resp.headers.get("ETag"))

    def to_draft(self, e) -> MediaItemDraft | None:
        body = ""
        if e.get("content"):
            body = max((c.get("value", "") for c in e.content), key=len)
        body = body or e.get("summary", "")
        return MediaItemDraft(
            external_id=e.get("id") or e.get("link"),
            url=e.get("link"),
            title=e.get("title"),
            published_at=struct_to_dt(e.get("published_parsed") or e.get("updated_parsed")),
            raw_text=html_to_text(body),
        )


class BlogAdapter(FeedAdapter):
    platform = Platform.blog


class PodcastAdapter(FeedAdapter):
    platform = Platform.podcast

    def to_draft(self, e) -> MediaItemDraft | None:
        draft = super().to_draft(e)
        audio = next(
            (
                lnk.href
                for lnk in e.get("enclosures", [])
                if lnk.get("type", "").startswith("audio")
            ),
            None,
        )
        if draft is None or audio is None:
            return None
        draft.extra["audio_url"] = audio
        draft.url = draft.url or audio
        return draft


class YouTubeAdapter(FeedAdapter):
    """Uses the public channel RSS feed. Handles may be '@handle' or a 'UC…' channel id."""

    platform = Platform.youtube
    _channel_ids: ClassVar[dict[str, str]] = {}  # handle -> channel id, shared across instances

    def resolve_channel_id(self, handle: str) -> str:
        if handle.startswith("UC"):
            return handle
        if handle not in self._channel_ids:
            resp = self.client.get(f"https://www.youtube.com/{handle}")
            resp.raise_for_status()
            m = re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', resp.text)
            if not m:
                raise ValueError(f"could not resolve YouTube channel id for {handle}")
            self._channel_ids[handle] = m.group(1)
        return self._channel_ids[handle]

    def feed_url(self, source: Source) -> str:
        cid = self.resolve_channel_id(source.handle)
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"

    def to_draft(self, e) -> MediaItemDraft | None:
        video_id = e.get("yt_videoid")
        if not video_id:
            return None
        if "/shorts/" in e.get("link", ""):
            return None  # shorts rarely carry substantive viewpoints
        desc = e.get("media_description") or e.get("summary", "")
        return MediaItemDraft(
            external_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=e.get("title"),
            published_at=struct_to_dt(e.get("published_parsed")),
            raw_text=desc,
        )


class ArxivAdapter(FeedAdapter):
    """handle is an arXiv search query, e.g. 'au:"Andrej Karpathy"'."""

    platform = Platform.arxiv

    def feed_url(self, source: Source) -> str:
        return (
            "https://export.arxiv.org/api/query?search_query="
            f"{quote_plus(source.handle)}&sortBy=submittedDate&sortOrder=descending&max_results=20"
        )

    def to_draft(self, e) -> MediaItemDraft | None:
        arxiv_id = e.get("id", "").rsplit("/abs/", 1)[-1]
        return MediaItemDraft(
            external_id=re.sub(r"v\d+$", "", arxiv_id),
            url=e.get("link"),
            title=" ".join(e.get("title", "").split()),
            published_at=struct_to_dt(e.get("published_parsed")),
            raw_text=" ".join(e.get("summary", "").split()),
        )
