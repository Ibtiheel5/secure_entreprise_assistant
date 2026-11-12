from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import log_access
from app.auth.deps import AuthContext, require_permission
from app.config import get_settings
from app.database.models import Classification, Department, Document, DocumentStatus, DocumentVersion
from app.documents import service
from app.documents.extract import InvalidFile
from app.permissions.acl import accessible_documents_clause
from app.database.session import get_db

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentOut(BaseModel):
    id: int
    title: str
    department: str
    classification: str
    status: str
    current_version: int | None
    updated_at: datetime
    allowed_roles: list[str] | None = None  # visible seulement pour les administrateurs de permissions


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class VersionOut(BaseModel):
    version_number: int
    status: str
    created_at: datetime


class PermissionsIn(BaseModel):
    allowed_roles: list[str]


class StatusIn(BaseModel):
    status: str


def to_out(db: Session, doc: Document, ctx: AuthContext | None = None, with_roles: bool = False) -> DocumentOut:
    dept = db.get(Department, doc.department_id)
    return DocumentOut(
        id=doc.id, title=doc.title, department=dept.code, classification=doc.classification, status=doc.status,
        current_version=service.active_version_number(db, doc.id), updated_at=doc.updated_at,
        allowed_roles=sorted(r.name for r in doc.allowed_roles) if with_roles else None)


def _can_write_dept(ctx: AuthContext, dept_code: str) -> bool:
    return "documents:manage_permissions" in ctx.permissions or ctx.user.department.code == dept_code


def _get_accessible(db: Session, ctx: AuthContext, doc_id: int, request: Request, action: str) -> Document:
    doc = db.scalar(select(Document).where(Document.id == doc_id, accessible_documents_clause(set(ctx.role_ids))))
    if doc is None:  # inexistant et interdit sont indiscernables
        log_access(db, action=action, allowed=False, user_id=ctx.user.id, resource_type="document",
                   resource_id=doc_id, reason="not_found_or_forbidden", request=request)
        raise HTTPException(404, "Document not found")
    return doc


def _err(exc: Exception):
    if isinstance(exc, InvalidFile):
        return HTTPException(422, str(exc))
    return HTTPException(getattr(exc, "status_code", 400), str(exc))


@router.get("", response_model=DocumentPage)
def list_documents(
    query: str | None = Query(None, max_length=200), department: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_permission("documents:read")), db: Session = Depends(get_db),
):
    where = [accessible_documents_clause(set(ctx.role_ids))]
    if query:
        where.append(Document.title.ilike(f"%{query}%"))
    if department:
        where.append(Document.department_id.in_(select(Department.id).where(Department.code == department)))
    total = db.scalar(select(func.count(Document.id)).where(*where)) or 0
    rows = db.scalars(select(Document).where(*where).order_by(Document.updated_at.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return DocumentPage(items=[to_out(db, d) for d in rows], total=total, page=page, page_size=page_size)


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request, file: UploadFile = File(...), title: str = Form(..., min_length=2, max_length=300),
    department_code: str = Form(...), classification: str = Form(Classification.INTERNAL),
    allowed_roles: str = Form(""), activate: bool = Form(True),
    ctx: AuthContext = Depends(require_permission("documents:write")), db: Session = Depends(get_db),
):
    if classification not in Classification.ALL:
        raise HTTPException(422, "Invalid classification")
    if not _can_write_dept(ctx, department_code):
        log_access(db, action="documents.upload", allowed=False, user_id=ctx.user.id,
                   reason="other_department", request=request)
        raise HTTPException(403, "Permission denied")
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()] or sorted(ctx.role_names)  # défaut : moindre privilège
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    try:
        doc = service.create_document(db, title=title, department_code=department_code, classification=classification,
                                      role_names=roles, created_by=ctx.user.id)
        service.add_version(db, doc, filename=file.filename or "", data=data, activate=activate)
    except (InvalidFile, service.DocumentError) as exc:
        db.rollback()
        raise _err(exc)
    log_access(db, action="documents.upload", allowed=True, user_id=ctx.user.id, resource_type="document",
               resource_id=doc.id, request=request)
    return to_out(db, doc)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, request: Request, ctx: AuthContext = Depends(require_permission("documents:read")),
                 db: Session = Depends(get_db)):
    return to_out(db, _get_accessible(db, ctx, doc_id, request, "documents.get"))


@router.get("/{doc_id}/versions", response_model=list[VersionOut])
def list_versions(doc_id: int, request: Request, ctx: AuthContext = Depends(require_permission("documents:read")),
                  db: Session = Depends(get_db)):
    """Métadonnées seulement : le contenu des anciennes versions n'est jamais servi ni indexé."""
    doc = _get_accessible(db, ctx, doc_id, request, "documents.versions")
    return [VersionOut(version_number=v.version_number, status=v.status, created_at=v.created_at)
            for v in sorted(doc.versions, key=lambda v: v.version_number, reverse=True)]


@router.post("/{doc_id}/versions", response_model=DocumentOut, status_code=201)
async def upload_version(
    doc_id: int, request: Request, file: UploadFile = File(...), activate: bool = Form(True),
    ctx: AuthContext = Depends(require_permission("documents:write")), db: Session = Depends(get_db),
):
    doc = db.get(Document, doc_id)
    dept = db.get(Department, doc.department_id).code if doc else None
    if doc is None or not _can_write_dept(ctx, dept):
        log_access(db, action="documents.new_version", allowed=False, user_id=ctx.user.id, resource_type="document",
                   resource_id=doc_id, reason="not_found_or_forbidden", request=request)
        raise HTTPException(404, "Document not found")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    try:
        service.add_version(db, doc, filename=file.filename or "", data=data, activate=activate)
    except (InvalidFile, service.DocumentError) as exc:
        db.rollback()
        raise _err(exc)
    log_access(db, action="documents.new_version", allowed=True, user_id=ctx.user.id, resource_type="document",
               resource_id=doc.id, request=request)
    return to_out(db, doc)


@router.put("/{doc_id}/permissions", response_model=DocumentOut)
def update_permissions(doc_id: int, body: PermissionsIn, request: Request,
                       ctx: AuthContext = Depends(require_permission("documents:manage_permissions")),
                       db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    try:
        service.set_permissions(db, doc, body.allowed_roles)
    except service.DocumentError as exc:
        raise _err(exc)
    log_access(db, action="documents.permissions", allowed=True, user_id=ctx.user.id, resource_type="document",
               resource_id=doc.id, request=request)
    return to_out(db, doc, ctx, with_roles=True)


@router.put("/{doc_id}/status", response_model=DocumentOut)
def update_status(doc_id: int, body: StatusIn, request: Request,
                  ctx: AuthContext = Depends(require_permission("documents:manage_permissions")),
                  db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    try:
        service.set_status(db, doc, body.status)
    except service.DocumentError as exc:
        raise _err(exc)
    log_access(db, action="documents.status", allowed=True, user_id=ctx.user.id, resource_type="document",
               resource_id=doc.id, reason=body.status, request=request)
    return to_out(db, doc, ctx, with_roles=True)
