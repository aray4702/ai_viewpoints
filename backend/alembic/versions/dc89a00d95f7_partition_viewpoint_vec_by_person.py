"""partition viewpoint_vec by person

Rebuilds the sqlite-vec table with a person_id partition key, so dedup's nearest-neighbour
lookup scans only the speaker's own viewpoints. Existing embeddings are copied over.

Revision ID: dc89a00d95f7
Revises: 21c158394f8f
Create Date: 2026-10-03 15:40:56.359785

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.config import get_settings
from app.core.db import vec_table_def

# revision identifiers, used by Alembic.
revision: str = "dc89a00d95f7"
down_revision: Union[str, Sequence[str], None] = "21c158394f8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rebuild(table_def: str, with_person: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT e.viewpoint_id, v.person_id, e.embedding FROM viewpoint_vec e "
            "JOIN viewpoints v ON v.id = e.viewpoint_id"
        )
    ).all()
    conn.execute(sa.text("DROP TABLE viewpoint_vec"))
    conn.execute(sa.text(f"CREATE VIRTUAL TABLE viewpoint_vec USING {table_def}"))
    for vid, pid, emb in rows:
        if with_person:
            conn.execute(
                sa.text(
                    "INSERT INTO viewpoint_vec(viewpoint_id, person_id, embedding) "
                    "VALUES (:id, :pid, :emb)"
                ),
                {"id": vid, "pid": pid, "emb": emb},
            )
        else:
            conn.execute(
                sa.text("INSERT INTO viewpoint_vec(viewpoint_id, embedding) VALUES (:id, :emb)"),
                {"id": vid, "emb": emb},
            )


def upgrade() -> None:
    _rebuild(vec_table_def(get_settings().embedding_dim), with_person=True)


def downgrade() -> None:
    dim = get_settings().embedding_dim
    _rebuild(
        f"vec0(viewpoint_id INTEGER PRIMARY KEY, embedding float[{dim}] distance_metric=cosine)",
        with_person=False,
    )
