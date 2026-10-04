MAX_VIEWPOINTS = 3

DOMAINS = [
    "ai",
    "semiconductors",
    "technology",
    "software",
    "investment",
    "stocks",
    "macro",
    "crypto",
    "business",
    "startups",
    "politics",
    "geopolitics",
    "policy",
    "science",
    "energy",
    "health",
    "education",
]

TRIAGE_SYSTEM = """You screen content for a service that tracks the viewpoints of influential thinkers.
Decide whether the given content contains at least one substantive viewpoint by the tracked person
or by a guest they interview: an opinion, prediction, judgment, recommendation, or argued position.

Not viewpoints: pure announcements ("new video out"), event logistics, sponsor reads,
link shares without commentary, jokes without a point, or an interviewer's questions.
When unsure, lean toward true: a later step does careful extraction."""

EXTRACT_SYSTEM = f"""You extract viewpoints from content authored by, or featuring, a tracked thinker.
A viewpoint is a distinct opinion, prediction, judgment, recommendation, or argued position held
by a specific person. Readers use these to quickly learn what people think, without consuming the
original media.

Rules:
- Credit every viewpoint to the person who actually holds it, in `speaker`:
  - In interviews and podcasts, guests' views are usually the most valuable. Extract them and
    credit the guest, even when the tracked person is the host.
  - A host's questions, summaries, and framing are not viewpoints. Credit the host only for views
    they clearly state as their own.
  - Use the speaker's full name as given in the content (e.g. "Noam Brown", not "Brown" or
    "the guest"). Skip views whose speaker you can't name.
  - For anyone other than the tracked person, fill speaker_bio with a one-line description drawn
    from the content (e.g. "Research scientist at OpenAI").
- Return at most {MAX_VIEWPOINTS} viewpoints, ordered from most to least valuable. This applies
  to long interviews too: pick the best, don't summarize everything.
- Every viewpoint must pass all three tests:
  1. Novel: a non-obvious, contrarian, or insider take, or a specific prediction. Skip
     conventional wisdom anyone in the field would already agree with ("AI is advancing fast",
     "fundamentals matter").
  2. Useful: specific enough to change how a reader thinks, with concrete reasoning, numbers,
     mechanisms, or named examples behind it. Skip vague generalities.
  3. Practical: a reader could act on it, e.g. a decision about what to build, invest in, learn,
     use, or watch for.
- Skip facts, anecdotes, and pleasantries with no stance. Returning fewer than {MAX_VIEWPOINTS},
  or none at all, is better than padding with weak viewpoints.
- Merge repeated statements of the same view into one viewpoint.
- verbatim_quote must be copied exactly from the source text, in the source's own language. Never
  translate it. It is checked by string matching, and viewpoints whose quote can't be found are
  discarded. Keep it under 60 words (or 120 characters for Chinese, Japanese, or Korean).
- Language: write claim, summary, topics, and entities in English, whatever the source language.
  When the quote is not in English, put an English translation in quote_translation; otherwise
  leave quote_translation null.
- Tags: a company or fund that has a ticker goes in tickers (with its name), not also in
  entities.
- Speaker names: credit the tracked person with their name exactly as given after "Tracked
  person". For anyone else, write the name as it appears in the content. For a name written in Chinese
  characters, use the characters (e.g. "徐梦迪"), not a romanization.
- The claim must stand alone: name the subject explicitly instead of using "it" or "this".
- State the claim directly as the view itself, not as reported speech: write "Reward hacking will
  get worse as RL scales", not "Brown argues that reward hacking will get worse".
- domains must come from this list: {", ".join(DOMAINS)}.
- Return an empty list when there are no real viewpoints."""


def triage_user(person: str, title: str | None, text: str) -> str:
    return f"Tracked person: {person}\nTitle: {title or '(none)'}\n\n<content>\n{text}\n</content>"


def extract_user(person: str, bio: str | None, platform: str, title: str | None, text: str) -> str:
    return (
        f"Tracked person: {person}\n"
        f"About them: {bio or '(unknown)'}\n"
        f"Platform: {platform}\nTitle: {title or '(none)'}\n\n"
        f"<content>\n{text}\n</content>"
    )
