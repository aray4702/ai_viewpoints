"""Claude calls for triage (Haiku) and viewpoint extraction (Sonnet)."""

from functools import lru_cache

import anthropic

from app.core.config import get_settings
from app.llm import prompts
from app.llm.schemas import ExtractionResult, TriageResult

# server-side refusal fallback: if a safety classifier declines, the API retries on another model
FALLBACK_BETA = "server-side-fallback-2026-07-01"
TRIAGE_CHARS = 12_000  # triage only needs the opening of long content


class LLMRefusal(Exception):
    pass


@lru_cache
def get_client() -> anthropic.Anthropic:
    key = get_settings().anthropic_api_key
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def _usage(resp) -> dict:
    u = resp.usage
    return {
        "model": resp.model,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_read_input_tokens": u.cache_read_input_tokens or 0,
        "cache_creation_input_tokens": u.cache_creation_input_tokens or 0,
    }


def _system(text: str) -> list[dict]:
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def triage(person: str, title: str | None, text: str) -> tuple[TriageResult, dict]:
    s = get_settings()
    resp = get_client().messages.parse(
        model=s.triage_model,
        max_tokens=512,
        system=_system(prompts.TRIAGE_SYSTEM),
        messages=[
            {"role": "user", "content": prompts.triage_user(person, title, text[:TRIAGE_CHARS])}
        ],
        output_format=TriageResult,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise LLMRefusal(f"triage stop_reason={resp.stop_reason}")
    return resp.parsed_output, _usage(resp)


def extract(
    person: str, bio: str | None, platform: str, title: str | None, text: str
) -> tuple[ExtractionResult, dict]:
    s = get_settings()
    resp = get_client().beta.messages.parse(
        model=s.extract_model,
        max_tokens=16_000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": s.extract_effort},
        system=_system(prompts.EXTRACT_SYSTEM),
        messages=[
            {"role": "user", "content": prompts.extract_user(person, bio, platform, title, text)}
        ],
        output_format=ExtractionResult,
    )
    if resp.stop_reason == "refusal":
        raise LLMRefusal(f"extraction refused: {getattr(resp.stop_details, 'category', None)}")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise RuntimeError(f"extraction incomplete: stop_reason={resp.stop_reason}")
    return resp.parsed_output, _usage(resp)
