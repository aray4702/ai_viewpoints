from typing import Literal

from pydantic import BaseModel, Field

from app.llm.prompts import MAX_VIEWPOINTS

Stance = Literal["bullish", "bearish", "positive", "negative", "neutral", "mixed", "prediction"]


class TriageResult(BaseModel):
    has_viewpoints: bool = Field(
        description="True if the tracked person or a guest expresses at least one substantive "
        "opinion, prediction, or argued position in this content."
    )
    reason: str


class Ticker(BaseModel):
    symbol: str = Field(description="Ticker symbol, uppercase, e.g. 'NVDA'.")
    company: str = Field(description="The company or fund it belongs to, e.g. 'Nvidia'.")


class ExtractedViewpoint(BaseModel):
    speaker: str = Field(description="Full name of the person who holds this viewpoint.")
    speaker_bio: str | None = Field(
        description="One-line description of the speaker from the content; null for the tracked "
        "person."
    )
    claim: str = Field(description="The viewpoint as one crisp, self-contained English sentence.")
    summary: str = Field(description="2-4 English sentences: the argument, reasoning, and context.")
    verbatim_quote: str = Field(
        description="An exact, contiguous excerpt from the source text supporting the claim, in "
        "the source's language. Copy it character-for-character; do not translate, paraphrase, "
        "or stitch fragments."
    )
    quote_translation: str | None = Field(
        description="English translation of verbatim_quote when the source isn't English, else null."
    )
    timestamp: str | None = Field(
        description="For transcripts, the [mm:ss] or [h:mm:ss] marker of the paragraph containing "
        "the quote, else null."
    )
    stance: Stance
    confidence: float = Field(description="How strongly the person holds it, 0.0-1.0.")
    domains: list[str] = Field(description="1-3 slugs from the domain list.")
    topics: list[str] = Field(description="1-5 short lowercase topic slugs, e.g. 'scaling-laws'.")
    entities: list[str] = Field(description="Companies, products, people, or orgs discussed.")
    tickers: list[Ticker] = Field(description="Stocks and funds discussed, by ticker.")


class ExtractionResult(BaseModel):
    viewpoints: list[ExtractedViewpoint] = Field(
        description=f"At most {MAX_VIEWPOINTS} novel, useful, practical viewpoints, most valuable first."
    )
