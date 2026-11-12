"""Schéma initial (Phase 1) + extension pgvector + index vectoriel HNSW.

Migration de base : crée le schéma complet à partir des modèles du moment.
Les migrations suivantes doivent être explicites (op.add_column, etc.), pas basées sur create_all.
"""
from alembic import op

from app.database import models  # noqa: F401
from app.database.session import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON document_chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
