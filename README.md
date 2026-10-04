<img src="web/app/icon.svg" alt="" width="64" height="64">

# Their Take

*What people think, with sources.*

Their Take watches people worth listening to across YouTube, podcasts, blogs, Substack, and
arXiv. It mines their media for novel, useful, practical viewpoints (at most three per item),
credits each to whoever actually said it, and publishes them with the exact quote and a link to
the source.

![The Their Take feed: viewpoint cards with a claim, a Show summary button, the original quote with a "Watch at 3:06" link and a Translate button, and tags](docs/images/demo.png)

## Quick start

```bash
cd backend
cp .env.example .env            # add ANTHROPIC_API_KEY (and GEMINI_API_KEY, VOYAGE_API_KEY)
uv sync && uv run alembic upgrade head && uv run python -m scripts.seed

uv run huey_consumer app.workers.tasks.huey -w 2 -k thread   # worker
uv run uvicorn app.main:app --port 8000                      # API (another terminal)
cd ../web && npm install && npm run dev                      # website on :3000 (another terminal)
```

## Documentation

- [Idea](docs/01-idea.md)
- [Requirements](docs/02-requirements.md)
- [Design](docs/03-design.md)
- [Implementation](docs/04-implementation.md)
- [User manual](docs/05-user-manual.md)

## Tests

```bash
cd backend && uv run pytest && uv run ruff check app tests scripts
cd web && npx tsc --noEmit && npm run lint
```

---

<sub>**Copyright.** © 2026 David Xu. All rights reserved. Viewpoints are summaries of publicly available media, each credited to its speaker and linked to its source. Quoted excerpts are kept short and remain the property of their speakers and publishers. To have content corrected or removed, contact the repository owner.</sub>
