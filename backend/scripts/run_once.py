"""Poll and process synchronously, without the queue. Handy for development.

uv run python -m scripts.run_once --person karpathy [--platform blog] [--limit 2]
"""

import argparse

from sqlalchemy import select

from app.core.db import session_scope
from app.models import Person, Platform, Source
from app.pipeline.poll import poll_source
from app.pipeline.process import process_item


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", required=True, help="person slug")
    ap.add_argument("--platform", choices=[p.value for p in Platform])
    ap.add_argument("--limit", type=int, default=2, help="max items to process per source")
    args = ap.parse_args()

    with session_scope() as db:
        q = select(Source).join(Person).where(Person.slug == args.person)
        if args.platform:
            q = q.where(Source.platform == Platform(args.platform))
        for src in db.scalars(q):
            new = poll_source(db, src)
            print(f"{src.platform.value} {src.handle}: {len(new)} new items")
            for item in new[: args.limit]:
                created = process_item(db, item)
                print(
                    f"  [{item.status.value}] {item.title!r} -> {len(created)} viewpoints"
                    + (f" ({item.error})" if item.error else "")
                )
                for vp in created:
                    print(f"    - {vp.claim}  [{', '.join(t.slug for t in vp.tags)}]")
            db.commit()


if __name__ == "__main__":
    main()
