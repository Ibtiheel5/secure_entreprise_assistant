"""Cycle de vie + versioning + indexation. Un seul état ACTIVE par document : activer une version archive les précédentes,
et la recherche ne lit que les chunks de la version ACTIVE."""
import hashlib
import os
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import (
    Department, Document, DocumentChunk, DocumentStatus, DocumentVersion, Role,
)
from app.documents.chunking import chunk_text
from app.documents.extract import extract_text, file_extension
from app.rag.embeddings import get_embedder


class DocumentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def create_document(db: Session, *, title: str, department_code: str, classification: str,
                    role_names: list[str], created_by: int | None, source: str = "upload",
                    external_id: str | None = None) -> Document:
    dept = db.scalar(select(Department).where(Department.code == department_code))
    roles = db.scalars(select(Role).where(Role.name.in_(role_names))).all()
    if dept is None:
        raise DocumentError("Unknown department", 422)
    if len(roles) != len(set(role_names)):
        raise DocumentError("Unknown role in allowed_roles", 422)
    doc = Document(title=title, department_id=dept.id, classification=classification,
                   status=DocumentStatus.DRAFT, source=source, created_by=created_by,
                   external_id=external_id, allowed_roles=list(roles))
    db.add(doc)
    db.flush()
    return doc


def _active_version(db: Session, doc_id: int) -> DocumentVersion | None:
    return db.scalar(select(DocumentVersion).where(
        DocumentVersion.document_id == doc_id, DocumentVersion.status == DocumentStatus.ACTIVE))


def add_version(db: Session, doc: Document, *, filename: str, data: bytes, activate: bool = True) -> DocumentVersion:
    if doc.status == DocumentStatus.DELETED:
        raise DocumentError("Document is deleted", 409)
    text = extract_text(filename, data)
    return add_version_from_text(db, doc, text=text, ext=file_extension(filename), raw=data, activate=activate)


def add_version_from_text(db: Session, doc: Document, *, text: str, ext: str = "txt",
                          raw: bytes | None = None, activate: bool = True) -> DocumentVersion:
    s = get_settings()
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    last = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
                      .order_by(DocumentVersion.version_number.desc())).first()
    if last and last.content_hash == content_hash:
        raise DocumentError("Identical to the latest version (duplicate)", 409)
    chunks = chunk_text(text, s.chunk_size, s.chunk_overlap)
    vectors = get_embedder().embed(chunks)  # avant toute écriture : pas d'état partiel si l'embedding échoue
    number = (last.version_number + 1) if last else 1

    file_path = None
    if raw is not None:
        d = Path(s.upload_dir) / str(doc.id)
        d.mkdir(parents=True, exist_ok=True)
        file_path = str(d / f"v{number}.{ext}")  # nom généré : jamais le nom fourni par l'utilisateur
        Path(file_path).write_bytes(raw)

    version = DocumentVersion(document_id=doc.id, version_number=number, status=DocumentStatus.DRAFT,
                              file_path=file_path, content_hash=content_hash)
    db.add(version)
    db.flush()
    db.add_all(DocumentChunk(document_id=doc.id, version_id=version.id, chunk_index=i, content=c, embedding=v)
               for i, (c, v) in enumerate(zip(chunks, vectors)))
    if activate:
        activate_version(db, doc, version)
    db.commit()
    return version


def activate_version(db: Session, doc: Document, version: DocumentVersion) -> None:
    for v in db.scalars(select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id, DocumentVersion.status == DocumentStatus.ACTIVE)):
        v.status = DocumentStatus.ARCHIVED
    version.status = DocumentStatus.ACTIVE
    doc.status = DocumentStatus.ACTIVE


def set_status(db: Session, doc: Document, new_status: str) -> None:
    if new_status not in DocumentStatus.ALL:
        raise DocumentError("Invalid status", 422)
    if doc.status == DocumentStatus.DELETED:
        raise DocumentError("Deleted documents cannot be restored", 409)
    if new_status == DocumentStatus.ACTIVE:
        latest = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
                            .order_by(DocumentVersion.version_number.desc())).first()
        if latest is None:
            raise DocumentError("Document has no version to activate", 409)
        activate_version(db, doc, latest)
    elif new_status == DocumentStatus.DELETED:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))  # purge de l'index
        for v in doc.versions:
            v.status = DocumentStatus.DELETED
            if v.file_path and os.path.exists(v.file_path):
                os.remove(v.file_path)
        doc.status = DocumentStatus.DELETED
    else:  # DRAFT / ARCHIVED
        for v in doc.versions:
            if v.status == DocumentStatus.ACTIVE:
                v.status = new_status
        doc.status = new_status
    db.commit()


def set_permissions(db: Session, doc: Document, role_names: list[str]) -> None:
    roles = db.scalars(select(Role).where(Role.name.in_(role_names))).all()
    if len(roles) != len(set(role_names)):
        raise DocumentError("Unknown role", 422)
    doc.allowed_roles = list(roles)
    db.commit()


def active_version_number(db: Session, doc_id: int) -> int | None:
    v = _active_version(db, doc_id)
    return v.version_number if v else None


def count_by_department(db: Session) -> dict[str, int]:
    rows = db.execute(select(Department.code, func.count(Document.id))
                      .join(Document, Document.department_id == Department.id, isouter=True)
                      .group_by(Department.code)).all()
    return {code: n for code, n in rows}
