"""
migrations/env.py
=================
Alembic migration environment for Feynman AI.

Configuration:
  - Reads DATABASE_URL from environment variable (Render Postgres in production).
  - Imports Base from database.py so autogenerate detects all ORM models.
  - Does NOT run against SQLite test databases — the test suite uses
    Base.metadata.create_all() for ephemeral SQLite DBs.

Zero-secret invariant: DATABASE_URL is read from env only; never hardcoded.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Ensure the project root is on sys.path so `database` can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

load_dotenv()

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all ORM models so autogenerate can detect schema changes
from database import Base  # noqa: E402  (import after sys.path setup)

# Expose Base.metadata for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """
    Read DATABASE_URL from environment.
    Falls back to the same default as database.py (SQLite dev DB) when
    DATABASE_URL is not set — so `alembic upgrade head` can be run locally
    during development without Postgres.
    """
    url = os.getenv("DATABASE_URL", "sqlite:///./feynman.db")
    # Render provides postgres:// URLs; SQLAlchemy 1.4+ requires postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live DB connection)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database connection."""
    # Override sqlalchemy.url in alembic.ini with the env var value
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
