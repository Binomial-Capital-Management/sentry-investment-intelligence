"""Alembic migration environment configuration.

Reads DATABASE_URL from environment and runs migrations synchronously.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from dotenv import load_dotenv

from alembic import context

# Load environment variables from .env file
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get DATABASE_URL from environment
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert asyncpg URL to psycopg2 for sync operations if needed
# Alembic uses synchronous connections
if database_url.startswith("postgresql://"):
    # Standard postgresql:// works with psycopg2
    sync_database_url = database_url
elif database_url.startswith("postgres://"):
    # Convert postgres:// to postgresql://
    sync_database_url = database_url.replace("postgres://", "postgresql://", 1)
else:
    sync_database_url = database_url

# Set the sqlalchemy.url in config (overriding alembic.ini)
# Escape % for ConfigParser (e.g., %23 in URL-encoded passwords becomes %%23)
escaped_url = sync_database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_url)

# add your model's MetaData object here for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
