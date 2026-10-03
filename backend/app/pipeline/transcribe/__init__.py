"""Turn a media item into text. YouTube: free captions first, then Gemini.
Podcasts: Gemini on the audio. Text platforms use the feed body as-is."""

import structlog

from app.models import MediaItem, Platform
from app.pipeline.transcribe.base import Transcript, TranscriptUnavailable

log = structlog.get_logger()


def _youtube_chain():
    from app.pipeline.transcribe.captions import CaptionsTranscriber
    from app.pipeline.transcribe.gemini import GeminiTranscriber

    return [CaptionsTranscriber, GeminiTranscriber]


def _podcast_chain():
    from app.pipeline.transcribe.gemini import GeminiTranscriber

    return [GeminiTranscriber]


def transcribe_item(item: MediaItem) -> Transcript:
    if item.platform == Platform.youtube:
        chain, kwargs = _youtube_chain(), {}
    elif item.platform == Platform.podcast:
        chain, kwargs = _podcast_chain(), {"audio_url": item.extra.get("audio_url")}
    else:
        if not item.raw_text:
            raise TranscriptUnavailable("no text")
        return Transcript(text=item.raw_text, provider="feed")

    errors = []
    for cls in chain:
        try:
            t = cls().transcribe(item.url, **kwargs)
            log.info("transcribed", item=item.id, provider=t.provider, chars=len(t.text))
            return t
        except TranscriptUnavailable as e:
            errors.append(f"{cls.__name__}: {e}")
    raise TranscriptUnavailable("; ".join(errors))


__all__ = ["Transcript", "TranscriptUnavailable", "transcribe_item"]
