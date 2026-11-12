"""Retrieval vectoriel avec filtre d'accès DANS la requête SQL.
Sur PostgreSQL : ACL en WHERE puis tri par distance pgvector (index HNSW). Sur SQLite (tests) : le même WHERE est appliqué
en SQL ; seul le tri par similarité est fait en Python sur des lignes DÉJÀ autorisées. Dans les deux cas un chunk
non autorisé n'est jamais lu."""
from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Department, Document, DocumentChunk, DocumentStatus, DocumentVersion,
)
from app.permissions.acl import accessible_documents_clause


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    title: str
    department: str
    classification: str
    version: int
    content: str
    score: float


def search_chunks(db: Session, role_ids: set[int] | frozenset[int], query_vector: list[float], top_k: int,
                  department_code: str | None = None, min_score: float | None = None) -> list[Hit]:
    stmt = (
        select(DocumentChunk, Document, DocumentVersion, Department.code)
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Department, Document.department_id == Department.id)
        .where(accessible_documents_clause(set(role_ids)))      # ACL : toujours dans la requête
        .where(DocumentVersion.status == DocumentStatus.ACTIVE)  # jamais d'ancienne version
    )
    if department_code:  # filtre fourni par l'utilisateur : ne peut que RESTREINDRE (AND), jamais élargir
        stmt = stmt.where(Department.code == department_code)

    if db.get_bind().dialect.name == "postgresql":
        dist = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = db.execute(stmt.add_columns(dist.label("d")).order_by(dist).limit(top_k)).all()
        hits = [Hit(c.id, d.id, d.title, dept, d.classification, v.version_number, c.content, float(1 - dist_))
                for c, d, v, dept, dist_ in rows]
        return [h for h in hits if min_score is None or h.score >= min_score]

    q = np.asarray(query_vector, dtype=np.float32)
    scored = []
    for c, d, v, dept in db.execute(stmt).all():
        if c.embedding is None:
            continue
        e = np.asarray(c.embedding, dtype=np.float32)
        denom = float(np.linalg.norm(q) * np.linalg.norm(e)) or 1.0
        scored.append(Hit(c.id, d.id, d.title, dept, d.classification, v.version_number, c.content,
                          float(q @ e) / denom))
    scored = [h for h in scored if min_score is None or h.score >= min_score]
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]
