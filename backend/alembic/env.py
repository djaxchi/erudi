"""Alembic environment for Erudi's embedded PostgreSQL cluster.

The database URL is only known at runtime (the embedded pgserver cluster picks a
port on boot — see ``src.launcher.postgres_runtime``), so this env does NOT read a
static URL from ``alembic.ini``. It takes the URL from, in order:

1. the option set by the programmatic runner (``src.database.migrations``), or
2. the ``ERUDI_ALEMBIC_URL`` env var (dev CLI: ``alembic revision --autogenerate``),
3. otherwise the (empty) ``alembic.ini`` placeholder.

Alembic owns ONLY the SQLAlchemy business tables (``Base.metadata``). The LangGraph
checkpointer tables and the ``rag`` vector-store schema are managed elsewhere and
are filtered out of autogenerate by ``include_name`` + ``include_schemas=False``.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.database.core import Base

# Side-effect import: pull every entity module so the full schema is registered on
# Base.metadata before autogenerate compares against the live database.
import src.entities as _entities

for _mod in pkgutil.iter_modules(_entities.__path__):
    if not _mod.name.startswith("_"):
        importlib.import_module(f"src.entities.{_mod.name}")

config = context.config

# Resolve the runtime URL (the programmatic runner sets it via set_main_option; the
# dev CLI uses ERUDI_ALEMBIC_URL). Never hardcode a production URL in alembic.ini.
_url = os.environ.get("ERUDI_ALEMBIC_URL") or config.get_main_option("sqlalchemy.url")
if _url:
    config.set_main_option("sqlalchemy.url", _url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Restrict autogenerate to the SQLAlchemy business tables.

    The LangGraph checkpointer tables (``checkpoints``, ``checkpoint_writes``, …)
    live in ``public`` alongside ours but are created by ``AsyncPostgresSaver.setup``;
    the ``rag`` schema is the PGVectorStore. Without this filter, autogenerate would
    propose DROPs for tables Alembic must not own.
    """
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    """Emit SQL without a DBAPI connection (``alembic upgrade --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=False,
        include_name=include_name,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=False,
            include_name=include_name,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
