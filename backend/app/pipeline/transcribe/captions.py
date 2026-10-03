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


PREFERRED = ("en", "zh")  # tie-breaker when the video's own language can't be told


def _base(code: str) -> str:
    return code.split("-")[0].lower()


def pick_track(tracks: list) -> object | None:
    """Choose the caption track in the video's own language, so quotes stay verbatim.

    YouTube makes one speech-recognition (generated) track, in the spoken language, which tells
    us the original language. Human-made tracks beat generated ones. Several generated tracks
    mean auto-dubbing, so the original language is unknown and PREFERRED breaks the tie.
    """
    generated = [t for t in tracks if t.is_generated]
    manual = [t for t in tracks if not t.is_generated]
    original = _base(generated[0].language_code) if len(generated) == 1 else None

    def rank(t) -> tuple[int, int]:
        base = _base(t.language_code)
        own = 0 if base == original else 1
        pref = PREFERRED.index(base) if base in PREFERRED else len(PREFERRED)
        return (own, pref)

    for group in (manual, generated):
        if group:
            return min(group, key=rank)
    return None


class CaptionsTranscriber:
    name = "youtube_captions"

    def __init__(self):
        self.api = YouTubeTranscriptApi()

    def transcribe(self, url: str, **_) -> Transcript:
        try:
            track = pick_track(list(self.api.list(video_id_from_url(url))))
            if track is None:
                raise TranscriptUnavailable("no usable caption track")
            fetched = track.fetch()
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
