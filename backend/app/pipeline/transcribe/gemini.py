"""Gemini transcription. Claude can't take video or audio input, so Gemini turns
YouTube videos (by URL) and podcast audio (uploaded) into timestamped text, which
Claude then mines like any other document."""

import tempfile
from pathlib import Path

import httpx
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.pipeline.transcribe.base import Transcript, TranscriptUnavailable

PROMPT = """Transcribe this {kind} verbatim in the language it is spoken in. Do not translate.
Format: one paragraph roughly every 30 seconds, each starting with a timestamp like [mm:ss] or [h:mm:ss].
Prefix each paragraph with the speaker's name if identifiable (e.g. "[12:30] Andrej Karpathy: ...").
{visual}Output only the transcript."""

VISUAL_NOTE = (
    "When slides, charts, or on-screen text convey information not spoken aloud, "
    'add it inline as "[on screen: ...]".\n'
)


class GeminiTranscriber:
    name = "gemini"

    def __init__(self):
        s = get_settings()
        if not s.gemini_api_key:
            raise TranscriptUnavailable("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=s.gemini_api_key)
        self.model = s.gemini_model

    def _run(self, media_part: types.Part, prompt: str) -> Transcript:
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=types.Content(parts=[media_part, types.Part(text=prompt)]),
            )
        except Exception as e:  # SDK raises several error types; any failure means "try next"
            raise TranscriptUnavailable(f"gemini error: {e}") from e
        if not resp.text:
            raise TranscriptUnavailable("gemini returned no text")
        um = resp.usage_metadata
        usage = {
            "model": self.model,
            "input_tokens": getattr(um, "prompt_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
        }
        return Transcript(text=resp.text.strip(), provider=self.name, usage=usage)

    def transcribe(self, url: str, *, audio_url: str | None = None, **_) -> Transcript:
        if audio_url:
            return self._transcribe_audio(audio_url)
        part = types.Part(file_data=types.FileData(file_uri=url))
        return self._run(part, PROMPT.format(kind="video", visual=VISUAL_NOTE))

    def _transcribe_audio(self, audio_url: str) -> Transcript:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episode.mp3"
            with httpx.stream("GET", audio_url, follow_redirects=True, timeout=300) as r:
                r.raise_for_status()
                with path.open("wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            uploaded = self.client.files.upload(file=path)
        try:
            part = types.Part(
                file_data=types.FileData(file_uri=uploaded.uri, mime_type=uploaded.mime_type)
            )
            return self._run(part, PROMPT.format(kind="podcast episode", visual=""))
        finally:
            self.client.files.delete(name=uploaded.name)
