from logging.config import fileConfig

from alembic import context

from app.core.db import engine
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# virtual tables (sqlite-vec, FTS5) and their shadow tables are managed by hand
VIRTUAL_PREFIXES = ("viewpoint_vec", "viewpoint_fts")


def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name and name.startswith(VIRTUAL_PREFIXES))


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite needs batch mode for ALTER
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
