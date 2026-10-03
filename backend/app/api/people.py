from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import admin_user
from app.api.schemas import (
    PersonDetail,
    PersonIn,
    PersonOut,
    SourceIn,
    SourceOut,
    SourcePatch,
)
from app.core.db import get_db
from app.models import Person, Source, Viewpoint

router = APIRouter(prefix="/api/people", tags=["people"])


def _counts(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Viewpoint.person_id, func.count())
        .where(Viewpoint.repeat_of_id.is_(None))
        .group_by(Viewpoint.person_id)
    )
    return dict(rows.all())


def _get(db: Session, slug: str) -> Person:
    p = db.scalar(select(Person).options(selectinload(Person.sources)).where(Person.slug == slug))
    if p is None:
        raise HTTPException(404, "person not found")
    return p


def _detail(p: Person, count: int) -> PersonDetail:
    return PersonDetail(
        **PersonOut.model_validate(p).model_dump(exclude={"viewpoint_count"}),
        viewpoint_count=count,
        sources=[SourceOut.model_validate(s) for s in p.sources],
    )


@router.get("", response_model=list[PersonOut])
def list_people(db: Session = Depends(get_db)):
    counts = _counts(db)
    people = db.scalars(select(Person).order_by(Person.name)).all()
    out = [
        PersonOut.model_validate(p).model_copy(update={"viewpoint_count": counts.get(p.id, 0)})
        for p in people
    ]
    return sorted(out, key=lambda p: -p.viewpoint_count)


@router.get("/{slug}", response_model=PersonDetail)
def get_person(slug: str, db: Session = Depends(get_db)):
    p = _get(db, slug)
    return _detail(p, _counts(db).get(p.id, 0))


# --- admin ---


@router.post("", response_model=PersonDetail, dependencies=[Depends(admin_user)])
def create_person(body: PersonIn, db: Session = Depends(get_db)):
    p = Person(**body.model_dump())
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "slug already exists") from None
    return _detail(_get(db, p.slug), 0)


@router.post("/{slug}/sources", response_model=SourceOut, dependencies=[Depends(admin_user)])
def add_source(slug: str, body: SourceIn, db: Session = Depends(get_db)):
    p = _get(db, slug)
    src = Source(person_id=p.id, **body.model_dump())
    db.add(src)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "source already exists") from None
    return SourceOut.model_validate(src)


@router.patch(
    "/{slug}/sources/{source_id}", response_model=SourceOut, dependencies=[Depends(admin_user)]
)
def update_source(slug: str, source_id: int, body: SourcePatch, db: Session = Depends(get_db)):
    p = _get(db, slug)
    src = db.get(Source, source_id)
    if src is None or src.person_id != p.id:
        raise HTTPException(404, "source not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(src, k, v)
    db.flush()
    return SourceOut.model_validate(src)
