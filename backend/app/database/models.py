from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database.session import Base

try:
    from pgvector.sqlalchemy import Vector

    EmbeddingType = Vector(get_settings().embedding_dim).with_variant(JSON(), "sqlite")
except ImportError:  # pragma: no cover
    EmbeddingType = JSON


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus:
    DRAFT, ACTIVE, ARCHIVED, DELETED = "DRAFT", "ACTIVE", "ARCHIVED", "DELETED"
    ALL = (DRAFT, ACTIVE, ARCHIVED, DELETED)


class Classification:
    PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED = "PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"
    ALL = (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)


def _in(col: str, values) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    permissions: Mapped[list[Permission]] = relationship(secondary="role_permissions", lazy="selectin")


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    hashed_password: Mapped[str] = mapped_column(String(255))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    department: Mapped[Department] = relationship(lazy="joined")
    roles: Mapped[list[Role]] = relationship(secondary="user_roles", lazy="selectin")


class RevokedToken(Base):
    """Liste de révocation des JWT (logout)."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)  # id d'origine du dataset
    title: Mapped[str] = mapped_column(String(300))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    classification: Mapped[str] = mapped_column(String(16), default=Classification.INTERNAL)
    status: Mapped[str] = mapped_column(String(16), default=DocumentStatus.DRAFT, index=True)
    source: Mapped[str] = mapped_column(String(64), default="upload")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    allowed_roles: Mapped[list[Role]] = relationship(secondary="document_permissions", lazy="selectin")

    __table_args__ = (
        CheckConstraint(_in("status", DocumentStatus.ALL), name="ck_documents_status"),
        CheckConstraint(_in("classification", Classification.ALL), name="ck_documents_classification"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=DocumentStatus.DRAFT)
    file_path: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    document: Mapped[Document] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        CheckConstraint(_in("status", DocumentStatus.ALL), name="ck_versions_status"),
    )


class DocumentChunk(Base):
    """Les droits d'un chunk sont ceux de son document parent (jointure, jamais de copie)."""
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(EmbeddingType, nullable=True)

    __table_args__ = (UniqueConstraint("version_id", "chunk_index", name="uq_chunk_position"),)


class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (CheckConstraint("role IN ('user','assistant')", name="ck_message_role"),)


class AccessLog(Base):
    __tablename__ = "access_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    allowed: Mapped[bool] = mapped_column(Boolean, index=True)
    reason: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class RelevanceExample(Base):
    __tablename__ = "relevance_examples"
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    passage: Mapped[str] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    label: Mapped[float] = mapped_column(Float)
    split: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(64))

    __table_args__ = (CheckConstraint("split IN ('train','val','test')", name="ck_example_split"),)


class ModelExperiment(Base):
    __tablename__ = "model_experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    model_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict | None] = mapped_column(JSON)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    is_deployed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
