"""Free YouTube captions via youtube-transcript-api."""

from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException

from app.pipeline.transcribe.base import Transcript, TranscriptUnavailable, fmt_ts

BLOCK_SECONDS = 30


def video_id_from_url(url: str) -> str:
    u = urlparse(url)
    if u.hostname == "youtu.be":
        return u.path.lstrip("/")
    return parse_qs(u.query).get("v", [u.path.rsplit("/", 1)[-1]])[0]


class CaptionsTranscriber:
    name = "youtube_captions"

    def __init__(self):
        self.api = YouTubeTranscriptApi()

    def transcribe(self, url: str, **_) -> Transcript:
        try:
            fetched = self.api.fetch(video_id_from_url(url), languages=["en", "en-US", "en-GB"])
        except YouTubeTranscriptApiException as e:
            raise TranscriptUnavailable(f"{type(e).__name__}") from e

        lines, block, block_start = [], [], None
        for snip in fetched.snippets:
            if block_start is None:
                block_start = snip.start
            block.append(snip.text.replace("\n", " "))
            if snip.start - block_start >= BLOCK_SECONDS:
                lines.append(f"[{fmt_ts(block_start)}] {' '.join(block)}")
                block, block_start = [], None
        if block:
            lines.append(f"[{fmt_ts(block_start)}] {' '.join(block)}")
        if not lines:
            raise TranscriptUnavailable("empty transcript")
        return Transcript(text="\n".join(lines), provider=self.name)
