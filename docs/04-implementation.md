# Implementation

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, managed with `uv`; FastAPI; SQLAlchemy 2 + Alembic; Pydantic v2 |
| Storage | SQLite (WAL mode) + `sqlite-vec` (vectors) + FTS5 (keyword search) |
| Jobs | `huey` with its SQLite backend |
| LLMs | Claude Haiku 4.5 (triage), Claude Sonnet 5.5 (extraction) via the `anthropic` SDK |
| Transcription | `youtube-transcript-api` (captions), Gemini via `google-genai` (video and audio) |
| Embeddings | Voyage `voyage-3` (1024 dimensions) |
| Web | Next.js 16 (App Router, server components) + Tailwind CSS 4 |
| Email | Resend (logs to the console when no key is set) |

## Code map

```
backend/
  app/
    core/        config.py (all settings, from .env), db.py (engine, WAL, sqlite-vec, FTS triggers)
    models/      tables.py: every table
    sources/     one adapter per platform: feeds.py (YouTube, blog, podcast, arXiv), html.py
    pipeline/
      poll.py          due_sources(), poll_source(): fetch and insert new items
      transcribe/      captions.py, gemini.py; __init__.py picks the chain per platform
      process.py       process_item(): the per-item pipeline, end to end
      quotes.py        quote verification (normalize + fuzzy match)
      speakers.py      speaker verification and crediting, guest auto-add
      tags.py          tag normalization
      embed.py         Voyage embeddings, sqlite-vec storage and nearest-neighbour lookup
    llm/         prompts.py (MAX_VIEWPOINTS, domains, prompts), schemas.py, client.py
    api/         viewpoints.py, people.py, auth.py, deps.py, schemas.py
    delivery/    email.py (Discord, digests, and RSS arrive in phase 5)
    workers/     tasks.py: periodic polling, per-item processing, stuck-item recovery
    main.py      FastAPI app
  alembic/       migrations
  scripts/       seed.py (load seeds/people.json), run_once.py (synchronous dev run)
  seeds/         people.json: the starting list of 20 people and 36 sources
  tests/         pytest suite: sources, pipeline, API
web/
  app/           pages: / (feed), /people, /people/[slug], /v/[id], /search, /login, /admin
  components/    ViewpointCard, Feed, FilterBar, AdminPanel, SignOutButton
  lib/           api.ts (server-side API client), types.ts, url.ts (filter URLs)
docs/            these documents
```

## How the main pieces work

### Polling (`pipeline/poll.py`, `workers/tasks.py`)

Every minute, `schedule_polls` finds active sources whose `last_polled_at + poll_interval_min`
has passed and queues a `poll` job for each. `poll_source` calls the platform adapter, skips
external ids already stored, skips items older than 14 days on a source's first poll, and queues
a `process` job per new item. Every 15 minutes, `retry_stuck` requeues items left mid-pipeline
for over an hour.

### Adapters (`sources/feeds.py`)

All current platforms read RSS/Atom with `feedparser`:

- **YouTube**: resolves an `@handle` to a channel id once (from the channel page), then reads
  `youtube.com/feeds/videos.xml`. Shorts are skipped.
- **Blog / Substack**: any feed URL; uses the longest content block (full post when available).
- **Podcast**: any RSS feed; items without an audio enclosure are skipped; the audio URL is
  stored in `media_items.extra`.
- **arXiv**: an API search query such as `au:"Yann LeCun"`; version suffixes are stripped so
  revisions don't duplicate.

To add a platform, subclass `SourceAdapter`, implement `fetch_new()`, and register it in
`sources/__init__.py`.

### Processing (`pipeline/process.py`)

`process_item` runs the steps in [Design → The pipeline](03-design.md#the-pipeline). Rules worth
knowing:

- Items under 200 characters of text are skipped; items over `MAX_INPUT_CHARS` (2M) fail rather
  than being silently truncated.
- Triage sees the first 12,000 characters; extraction sees everything.
- Token usage for each stage is saved in `media_items.llm_usage` for cost tracking.
- The function commits after each stage. SQLite allows one writer at a time, holding the lock
  from a transaction's first write until commit, so nothing may be left uncommitted while
  waiting on transcription, Claude, or Voyage. Otherwise polls, sign-ins, and admin edits would
  stall behind long LLM calls.
- Platforms without an adapter yet (X, Reddit) are skipped when looking for sources to poll.
- Transient Claude errors (rate limits, connection, server errors) are retried by the job queue
  up to 3 times; any other error marks the item `failed` with the error text.

### Extraction prompt (`llm/prompts.py`)

The prompt is the main quality lever. It defines novel / useful / practical, caps output at
`MAX_VIEWPOINTS` (3), requires direct claims rather than "X argues that…", and requires crediting
guests by full name. The response schema is in `llm/schemas.py`. Both system prompts are marked
for prompt caching.

### Search (`api/viewpoints.py`)

`/api/viewpoints?q=` uses FTS5 keyword matching. `/api/search` runs FTS5 and vector search,
then merges the two rankings with reciprocal rank fusion. Without a Voyage key, it falls back
to keyword-only.

### Auth (`api/auth.py`, `api/deps.py`)

The magic link carries a signed, 15-minute token. Discord uses OAuth with the `identify email`
scopes, and links to an existing account when the verified email matches. Both end by setting a
signed session cookie, valid for 30 days.

## API reference

| Method & path | Purpose | Auth |
|---|---|---|
| `GET /api/viewpoints` | Feed. Params: `person`, `tag`, `domain` (repeatable, AND-combined), `q`, `include_repeats`, `cursor`, `limit` | — |
| `GET /api/viewpoints/{id}` | One viewpoint | — |
| `GET /api/search?q=` | Hybrid search | — |
| `GET /api/tags?q=&kind=` | Tags by usage, for autocomplete | — |
| `GET /api/people` | People with viewpoint counts | — |
| `GET /api/people/{slug}` | Person with sources | — |
| `POST /api/people` | Add a person | admin |
| `POST /api/people/{slug}/sources` | Add a source | admin |
| `PATCH /api/people/{slug}/sources/{id}` | Pause/resume or change interval | admin |
| `POST /api/auth/magic-link` | Email a sign-in link | — |
| `GET /api/auth/verify?token=` | Complete email sign-in | — |
| `GET /api/auth/discord/login` | Start Discord sign-in | — |
| `GET /api/auth/me` · `POST /api/auth/logout` | Current user · sign out | user |
| `GET /api/health` | Liveness check | — |

Interactive docs are at `http://localhost:8000/docs` while the API runs.

## Configuration

All settings are read from `backend/.env` (template: `backend/.env.example`). Main ones:

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for triage and extraction |
| `GEMINI_API_KEY` | — | Video without captions, podcast audio |
| `VOYAGE_API_KEY` | — | Dedup and meaning-based search (optional) |
| `TRIAGE_MODEL` / `EXTRACT_MODEL` | `claude-haiku-4-5` / `claude-sonnet-5-5` | Models |
| `EXTRACT_EFFORT` | `medium` | Extraction effort: `low`, `medium`, `high` |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Transcription model |
| `DEDUP_SIMILARITY` / `DEDUP_WINDOW_DAYS` | `0.90` / `90` | Repeat detection |
| `QUOTE_MATCH_THRESHOLD` | `90` | Fuzzy quote match score (0–100) |
| `SECRET_KEY` | placeholder | Signs sessions; **must** be set in production |
| `ADMIN_EMAILS` | `[]` | JSON list of admin email addresses |
| `WEB_BASE_URL` | `http://localhost:3000` | Base for links in emails and OAuth redirects |
| `RESEND_API_KEY`, `EMAIL_FROM` | — | Email sending |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` | — | Discord sign-in |
| `DATA_DIR` | `backend/data` | Where the database and queue files live |

The web app reads `API_URL` (default `http://127.0.0.1:8000`).

## Testing

```bash
cd backend && uv run pytest && uv run ruff check app tests scripts
cd web && npx tsc --noEmit && npm run lint
```

The 31 backend tests use a temporary database, mocked HTTP feeds, and mocked LLM responses, so
they need no keys or network. They cover the adapters, quote and speaker verification, guest
crediting, tagging, deduplication (including that it only compares a person with themselves),
polling idempotency, that no database lock is held during LLM calls, that token usage is saved, and every API endpoint including auth
and admin checks.

Extraction quality can only be judged against real content: run `scripts/run_once.py` on a few
items and read the results.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1. Foundation | Schema, migrations, config, seed data | Done |
| 2. Ingestion | YouTube, podcast, blog, arXiv adapters; transcription; scheduled polling | Done |
| 3. Extraction | Triage, extraction, quote and speaker checks, guest crediting, tagging, dedup | Done |
| 4. API + web | REST API, website, search, sign-in, admin | Done |
| 5. Subscriptions | Filter language, matching, Discord bot, email digests, RSS | Next |
| 6. Reddit + X | Two more adapters (X behind a swappable provider, due to API cost) | Planned |
| 7. Hardening | Rate limits, monitoring, CI, re-running extraction from admin, speaker checks on video clips with fuzzy name matching (see known limitations) | Planned |

## Known limitations

- **Speaker credit on YouTube videos with several speakers (postponed).** YouTube captions have
  no speaker labels, so Claude infers who said what from context. Tested 2026-10-03:
  - One-guest interview (Noam Brown): 3 of 3 credited correctly.
  - Two-guest episode (Alex Imas and Phil Trammell): 2 of 3; one of Imas's views was credited
    to Trammell.
  - Gemini watching the whole video credited 3 of 3 correctly, but at about 5x the cost (~$0.35
    vs ~$0.06 per 80-minute episode), and 2 of its 3 "verbatim" quotes were paraphrased.
  - **Planned fix:** keep captions → Claude for extraction, then have Gemini identify the
    speaker on a ~60-second clip around each quote (about $0.015 per episode).
- **Speaker check rejects misspelled names (postponed, same fix).** Captions spell names as
  heard (e.g. "Sax" for Sacks, "Freeberg" for Friedberg). The exact-surname check in
  `pipeline/speakers.py` then discards every viewpoint from those speakers, so All-In co-hosts
  are lost. **Planned fix:** fuzzy surname matching, and also accepting names listed in the
  tracked person's bio.

- **Same episode, two platforms.** An episode published on both YouTube and Substack is
  extracted twice. Repeated viewpoints are caught by dedup, but the LLM cost is paid twice.
- **Name collisions.** Two different people with the same name would be merged into one person.
- **Auto-added guests have no sources.** They only appear through other people's media until an
  admin adds sources for them.
- **Reusable sign-in links** within their 15-minute window.
- **Single host.** SQLite means one machine. Back up with Litestream, or move to Postgres if
  the project outgrows it.
