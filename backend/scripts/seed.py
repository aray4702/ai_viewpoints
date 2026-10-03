"""Load people and sources from seeds/people.json. Safe to re-run (upserts by slug / handle)."""

import json
from pathlib import Path

from sqlalchemy import select

from app.core.db import session_scope
from app.models import Person, Platform, Source

SEED_FILE = Path(__file__).resolve().parents[1] / "seeds" / "people.json"


def main() -> None:
    data = json.loads(SEED_FILE.read_text())
    with session_scope() as db:
        for p in data:
            person = db.scalar(select(Person).where(Person.slug == p["slug"]))
            if person is None:
                person = Person(slug=p["slug"])
                db.add(person)
            person.name, person.bio, person.domains = p["name"], p.get("bio"), p.get("domains", [])
            db.flush()
            for s in p.get("sources", []):
                platform = Platform(s["platform"])
                src = db.scalar(
                    select(Source).where(Source.platform == platform, Source.handle == s["handle"])
                )
                if src is None:
                    src = Source(platform=platform, handle=s["handle"])
                    db.add(src)
                src.person_id = person.id
                src.poll_interval_min = s.get("poll_interval_min", 60)
        print(f"seeded {len(data)} people")


if __name__ == "__main__":
    main()
