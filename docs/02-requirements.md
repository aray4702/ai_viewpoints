# Requirements

Status key: **Done** is built and tested; **Planned** is scheduled in a later phase (see
[Implementation](04-implementation.md#roadmap)).

## Users

| User | Needs |
|---|---|
| **Reader** | Browse, filter, and search viewpoints without an account. |
| **Subscriber** | Sign in and get new viewpoints that match their interests delivered to them. |
| **Admin** | Choose whom to track and on which platforms; review automatically added guests. |
| **Operator** | Run, configure, and monitor the system at low cost. |

## Functional requirements

### Watching sources

| ID | Requirement | Status |
|---|---|---|
| S1 | Track a list of people, each with one or more sources. | Done |
| S2 | Supported sources: YouTube channels, podcasts (RSS), blogs and Substack (RSS/Atom), arXiv author queries. | Done |
| S3 | Supported sources: Reddit users and X accounts. | Planned |
| S4 | Poll each source on its own interval and pick up only new media. | Done |
| S5 | On a source's first poll, take only recent media (last 14 days), not its whole history. | Done |
| S6 | Admins can add people and sources and pause or resume a source without code changes. | Done |

### Mining viewpoints

| ID | Requirement | Status |
|---|---|---|
| M1 | Turn video and audio into text with timestamps. Use free YouTube captions first; fall back to Gemini for videos without captions and for podcast audio. | Done |
| M2 | Skip media with no substantive opinions (announcements, sponsor reads) before running the expensive extraction step. | Done |
| M3 | Extract at most 3 viewpoints per media item, each novel, useful, and practical, ranked by value. | Done |
| M4 | Each viewpoint has a standalone claim, a 2–4 sentence summary, an exact supporting quote, a timestamp when available, a stance, and tags. | Done |
| M5 | Credit each viewpoint to the person who holds it. Interview guests get credit for their own views; a host's questions are not viewpoints. | Done |
| M6 | Add guests who aren't tracked yet as new people automatically, marked as auto-added. | Done |
| M7 | Discard any viewpoint whose quote can't be found in the source, or whose speaker isn't named in it. | Done |
| M8 | Tag each viewpoint by domain (fixed list), topic, entity, and stock ticker, without tagging a company twice (as name and ticker). | Done |
| M9 | Detect when a person repeats a view they expressed in the last 90 days, and mark it as a repeat instead of new. | Done |

### Publishing and finding

| ID | Requirement | Status |
|---|---|---|
| P1 | A public website with a newest-first feed. | Done |
| P2 | Filter the feed by person, tag, and domain; combine filters. | Done |
| P3 | Search by keywords and by meaning (hybrid search). | Done |
| P4 | A page per person and per viewpoint. | Done |
| P5 | Post new viewpoints to Discord channels. | Planned |
| P6 | Non-English sources (e.g. Chinese channels) appear in English, with the original quote and an English translation on request. | Done |
| P7 | Cards are scannable: claim and quote up front; the summary and translation on request; a clearly labelled source link that opens at the quote's timestamp. | Done |

### Subscriptions

| ID | Requirement | Status |
|---|---|---|
| U1 | Sign in by email link or Discord. | Done |
| U2 | Subscribe with a filter expression, e.g. `karpathy`, `stock & semiconductor`, `topic:ai \| ticker:NVDA`. | Planned |
| U3 | Delivery by Discord DM, email digest (daily or weekly), and a personal RSS feed. | Planned |
| U4 | Never deliver the same viewpoint twice to the same subscriber and channel. | Planned |

## Non-functional requirements

| ID | Requirement | Status |
|---|---|---|
| N1 | **Lightweight to run**: one SQLite file, no database or queue server. | Done |
| N2 | **Cost control**: cheap screening model before the extraction model; free captions before paid transcription; at most 3 viewpoints per item. | Done |
| N3 | **Traceability**: every viewpoint links to its source and records the LLM tokens spent on its media item. | Done |
| N4 | **Idempotent**: re-polling never creates duplicate media; restarting the worker resumes half-processed items. | Done |
| N5 | **Copyright-conscious**: publish short quotes and links, not full transcripts. | Done |
| N6 | **Swappable providers**: transcription, LLM models, and embedding models are configurable. | Done |
| N7 | Works on phone-sized screens and in light and dark mode. | Built; not yet checked on real devices |
| N8 | Retries for transient failures. | Done (basic job retries) |
| N9 | Per-platform rate limits, error monitoring, CI. | Planned |
