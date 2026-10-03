"""Guard against hallucinated quotes: every quote must be found (fuzzily) in the source."""

import re

from rapidfuzz import fuzz

_TS = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")
_SPEAKER = re.compile(r"(?m)^\s*[A-Z][\w.'\- ]{0,40}:\s")


def normalize(text: str) -> str:
    text = _TS.sub(" ", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"')
    text = text.replace("”", '"').replace("—", "-").replace("–", "-")
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return " ".join(text.split())


def quote_in_source(quote: str, source: str, threshold: float) -> bool:
    q, src = normalize(quote), normalize(_SPEAKER.sub(" ", source))
    if not q:
        return False
    if q in src:
        return True
    # tolerate transcript noise and quotes spanning a timestamp/speaker boundary
    return fuzz.partial_ratio(q, src) >= threshold
