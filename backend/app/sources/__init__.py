from app.models import Platform
from app.sources.base import FetchResult, MediaItemDraft, SourceAdapter
from app.sources.feeds import ArxivAdapter, BlogAdapter, PodcastAdapter, YouTubeAdapter

# reddit and x adapters land in phase 6
ADAPTERS: dict[Platform, type[SourceAdapter]] = {
    Platform.youtube: YouTubeAdapter,
    Platform.podcast: PodcastAdapter,
    Platform.blog: BlogAdapter,
    Platform.arxiv: ArxivAdapter,
}


def get_adapter(platform: Platform) -> SourceAdapter | None:
    cls = ADAPTERS.get(platform)
    return cls() if cls else None


__all__ = ["ADAPTERS", "FetchResult", "MediaItemDraft", "SourceAdapter", "get_adapter"]
