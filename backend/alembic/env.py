from alembic import context

from app.config import get_settings
from app.database import models  # noqa: F401  (enregistre les tables)
from app.database.session import Base, engine

target_metadata = Base.metadata
get_settings()  # échoue tôt si l'environnement est incomplet


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
