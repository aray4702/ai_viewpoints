from dataclasses import dataclass
from typing import Protocol


class TranscriptUnavailable(Exception):
    """This transcriber can't produce a transcript for the item; try the next one."""


@dataclass
class Transcript:
    text: str  # lines formatted as "[mm:ss] ..." when timestamps are known
    provider: str
    usage: dict | None = None


class Transcriber(Protocol):
    name: str

    def transcribe(self, url: str, **kwargs) -> Transcript: ...


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_ts(ts: str) -> int | None:
    """'1:02:03' or '02:03' -> seconds."""
    try:
        parts = [int(p) for p in ts.strip().strip("[]").split(":")]
    except ValueError:
        return None
    total = 0
    for p in parts:
        total = total * 60 + p
    return total
