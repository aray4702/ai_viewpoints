# User manual

- [For readers](#for-readers): browsing, filtering, searching
- [For admins](#for-admins): choosing whom to track
- [For operators](#for-operators): installing and running Their Take

---

## For readers

### The feed

The home page lists the newest viewpoints first. Each card shows:

- **Who holds the view**, the platform, and the date. If the view came from someone else's show
  or blog, the card says so, e.g. *Noam Brown · Blog via Dwarkesh Patel*.
- **The claim**: the viewpoint in one sentence. Click it for the viewpoint's own page.
- **A short summary** of the reasoning.
- **The exact quote**, with a link to the source. Quotes from non-English sources are shown in
  the original language with an English translation underneath. For YouTube, the link jumps to the moment the
  quote is spoken.
- **Tags**: domains (highlighted), topics, companies and people mentioned, and stock tickers
  (shown with `$`).
- **Stance**, when there is one: bullish, bearish, positive, negative, mixed, or prediction.

Click **Older →** at the bottom for the next page.

### Filtering

- **Click any tag** on a card to show only viewpoints with that tag. Click more tags to narrow
  further. Every active filter must match.
- **Click a name** to open that person's page.
- **Type in the search box** on the feed to filter by words.
- Active filters appear as chips under the search box. Click a chip to remove it, or
  **Clear all**.

Filtered views have their own URL, so you can bookmark or share them, e.g.
`/?domain=semiconductors&tag=nvda`.

### Search

**Search** in the top menu finds viewpoints by meaning as well as by words. Try a question, such
as *will GPU prices fall?*

### People

**People** lists everyone with viewpoints, most prolific first. A person's page shows their
bio, links to their channels and feeds, and all their viewpoints.

People marked **Guest** were added automatically after appearing on a tracked person's show.
Their viewpoints come from other people's media.

### Signing in

Click **Sign in** and either enter your email to receive a link (valid 15 minutes), or use
**Continue with Discord**. You stay signed in for 30 days. Subscriptions, arriving in a coming
release, will need an account; browsing doesn't.

---

## For admins

Admins are the email addresses listed in the `ADMIN_EMAILS` setting. After signing in with one
of them, an **Admin** link appears in the menu.

### Add a person

Under **Add a person**, enter a name, an optional one-line bio, and domains separated by commas
(e.g. `ai, semiconductors`). Domains should come from: ai, semiconductors, technology, software,
investment, stocks, macro, crypto, business, startups, politics, geopolitics, policy, science,
energy, health, education.

### Add a source

Under each person, pick a platform and enter:

| Platform | Enter | Example |
|---|---|---|
| youtube | the channel's `@handle` | `@AndrejKarpathy` |
| blog | the RSS/Atom feed URL | `https://www.oneusefulthing.org/feed` |
| podcast | the podcast's RSS feed URL | `https://lexfridman.com/feed/podcast/` |
| arxiv | an arXiv author query | `au:"Yann LeCun"` |

Set how often to check it, in minutes. Busy accounts can use 30–60; most blogs and channels are
fine at 360 (6 hours) or more.

Tips:

- **Other languages:** channels in Chinese and other languages work. Viewpoints appear in
  English, with the original quote and an English translation.
- **Substack:** add `/feed` to the publication's URL.
- **Finding a feed:** many sites link one as "RSS". For podcasts, the feed URL is listed on the
  show's page in most podcast directories.
- **First check:** a new source only picks up items from the last 14 days, so adding a prolific
  channel won't trigger a flood of processing.

### Pause a source

Click **Pause** next to a source to stop checking it; **Resume** turns it back on. Existing
viewpoints are kept.

### Review guests

People marked **added as a guest** were created automatically. You can add sources for them to
track them directly. There is no merge or delete in the admin page yet. If a guest duplicates an
existing person under a different spelling, tell an operator.

---

## For operators

### Requirements

- macOS or Linux, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 20+
- API keys: Anthropic (required), Gemini (for videos without captions and for podcasts), Voyage
  (optional, for dedup and meaning-based search)

### Install

```bash
cd backend
cp .env.example .env          # then fill in keys and settings
uv sync
uv run alembic upgrade head   # create or upgrade the database
uv run python -m scripts.seed # load the starting list of people (safe to re-run)

cd ../web
npm install
```

### Run

Three processes, in separate terminals:

```bash
cd backend && uv run huey_consumer app.workers.tasks.huey -w 2 -k thread   # worker
cd backend && uv run uvicorn app.main:app --port 8000                      # API
cd web && npm run dev                                                      # website on :3000
```

For production, build the website with `npm run build && npm start`, set `SECRET_KEY`,
`WEB_BASE_URL`, and `API_URL`, and serve it over HTTPS.

### Try one person without the worker

```bash
cd backend
uv run python -m scripts.run_once --person dwarkesh-patel --platform blog --limit 1
```

This polls that person's sources and processes up to `--limit` new items per source, printing
each viewpoint. It only processes items it hasn't seen before.

### Change who is tracked in bulk

Edit `backend/seeds/people.json` and re-run `uv run python -m scripts.seed`. Existing people and
sources are updated, new ones added; nothing is deleted.

### Set up email and Discord sign-in

- **Email:** create a Resend API key, verify your sending domain, and set `RESEND_API_KEY` and
  `EMAIL_FROM`. Without a key, sign-in links are printed in the API log, which is handy for
  local use.
- **Discord:** create an application at discord.com/developers, add the redirect
  `<WEB_BASE_URL>/api/auth/discord/callback`, and set `DISCORD_CLIENT_ID` and
  `DISCORD_CLIENT_SECRET`.

### Tune quality and cost

| To… | Change |
|---|---|
| Get more or fewer viewpoints per item | `MAX_VIEWPOINTS` in `backend/app/llm/prompts.py` |
| Change what counts as a good viewpoint | `EXTRACT_SYSTEM` in the same file |
| Trade extraction cost for depth | `EXTRACT_EFFORT` = `low`, `medium`, or `high` |
| Be stricter or looser about repeats | `DEDUP_SIMILARITY` (higher = fewer repeats detected) |
| Check sources less often | the poll interval on each source |

Each media item records the tokens it used in `media_items.llm_usage`.

### Monitor

```bash
sqlite3 backend/data/viewpoints.db \
  "select status, count(*) from media_items group by 1;"
sqlite3 backend/data/viewpoints.db \
  "select title, error from media_items where status in ('failed','skipped') order by id desc limit 20;"
```

- `skipped` is normal: no transcript, too short, or no viewpoints found.
- `failed` needs a look: the `error` column says why.

### Back up

The database is the single file `backend/data/viewpoints.db`. Copy it safely while running
with:

```bash
sqlite3 backend/data/viewpoints.db ".backup backup.db"
```

For continuous backups to S3, use Litestream.

### Upgrade

After pulling new code:

```bash
cd backend && uv sync && uv run alembic upgrade head
cd ../web && npm install
```

Then restart all three processes.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| A YouTube source never yields items | Wrong `@handle`. Open `youtube.com/<handle>` to check. |
| Videos are `skipped` with "no transcript" | No captions and no `GEMINI_API_KEY`, or Gemini couldn't read the video. |
| Many viewpoints are dropped | The model's quotes didn't match the source. Check the `viewpoints_unverified` log lines. |
| Search ignores meaning | `VOYAGE_API_KEY` is not set, so search is keyword-only. |
| Sign-in link not received | No `RESEND_API_KEY`: look for the link in the API log. |
| "database is locked" errors | More than one worker process. Run a single worker. |
