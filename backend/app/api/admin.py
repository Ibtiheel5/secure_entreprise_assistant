from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.documents import DocumentPage, to_out
from app.api.users import to_out as user_out
from app.api.schemas import UserOut
from app.audit.service import log_access
from app.auth.deps import AuthContext, require_permission
from app.database.models import Document, Role, User
from app.documents.service import count_by_department
from app.database.session import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RolesIn(BaseModel):
    roles: list[str]


@router.get("/stats")
def stats(ctx: AuthContext = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Document.status, func.count(Document.id)).group_by(Document.status)).all())
    return {"total_users": db.scalar(select(func.count(User.id))) or 0,
            "total_documents": db.scalar(select(func.count(Document.id))) or 0,
            "documents_by_department": count_by_department(db), "documents_by_status": by_status}


@router.get("/roles")
def roles(ctx: AuthContext = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    return [{"name": r.name, "description": r.description, "permissions": sorted(p.code for p in r.permissions)}
            for r in db.scalars(select(Role).order_by(Role.name))]


@router.get("/documents", response_model=DocumentPage)
def admin_documents(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    ctx: AuthContext = Depends(require_permission("documents:manage_permissions")),
                    db: Session = Depends(get_db)):
    """Gestion : métadonnées et ACL uniquement, jamais le contenu."""
    total = db.scalar(select(func.count(Document.id))) or 0
    rows = db.scalars(select(Document).order_by(Document.id).offset((page - 1) * page_size).limit(page_size)).all()
    return DocumentPage(items=[to_out(db, d, ctx, with_roles=True) for d in rows], total=total, page=page,
                        page_size=page_size)


@router.put("/users/{user_id}/roles", response_model=UserOut)
def set_user_roles(user_id: int, body: RolesIn, request: Request,
                   ctx: AuthContext = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    roles_ = db.scalars(select(Role).where(Role.name.in_(body.roles))).all()
    if user is None:
        raise HTTPException(404, "User not found")
    if not body.roles or len(roles_) != len(set(body.roles)):
        raise HTTPException(422, "Unknown role")
    user.roles = list(roles_)
    db.commit()
    log_access(db, action="users.set_roles", allowed=True, user_id=ctx.user.id, resource_type="user",
               resource_id=user.id, request=request)
    return user_out(user)
