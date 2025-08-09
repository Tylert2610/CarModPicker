from logging.config import fileConfig
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import create_engine
from alembic import context

# Add the app directory to Python path so we can import app modules
sys.path.insert(0, "/app")

# Load .env file variables into environment
# Assumes .env is in the project root (one level up from alembic dir)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get the database URL from the environment variable
# Fallback to DATABASE_URL if ALEMBIC_DATABASE_URL is not set, then to the value in alembic.ini
ALEMBIC_DATABASE_URL = (
    os.getenv("ALEMBIC_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
)


if not ALEMBIC_DATABASE_URL:
    raise ValueError(
        "Neither ALEMBIC_DATABASE_URL nor DATABASE_URL environment variables are set, and sqlalchemy.url is not configured in alembic.ini"
    )


config.set_main_option("sqlalchemy.url", ALEMBIC_DATABASE_URL)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:

    context.configure(
        url=ALEMBIC_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:

    connectable = create_engine(str(ALEMBIC_DATABASE_URL), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
