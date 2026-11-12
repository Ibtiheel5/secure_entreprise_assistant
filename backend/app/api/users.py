from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import Page, UserCreate, UserOut
from app.audit.service import log_access
from app.auth.deps import AuthContext, get_auth_context, require_permission
from app.database.models import Department, Role, User
from app.database.session import get_db
from app.security.passwords import hash_password

router = APIRouter(prefix="/api", tags=["users"])


def to_out(user: User, permissions: list[str] | None = None) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name,
        department=user.department.code, roles=sorted(r.name for r in user.roles),
        permissions=sorted(permissions or []),
    )


@router.get("/auth/me", response_model=UserOut)
@router.get("/users/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(get_auth_context)):
    return to_out(ctx.user, list(ctx.permissions))


@router.get("/users", response_model=Page)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthContext = Depends(require_permission("users:read")),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(User.id))) or 0
    rows = db.scalars(select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=[to_out(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    request: Request,
    ctx: AuthContext = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    dept = db.scalar(select(Department).where(Department.code == body.department_code))
    roles = db.scalars(select(Role).where(Role.name.in_(body.roles))).all()
    if dept is None or len(roles) != len(set(body.roles)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown department or role")
    user = User(email=body.email.lower(), full_name=body.full_name,
                hashed_password=hash_password(body.password), department_id=dept.id, roles=list(roles))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    log_access(db, action="users.create", allowed=True, user_id=ctx.user.id,
               resource_type="user", resource_id=user.id, request=request)
    return to_out(user)


@router.get("/users/me/access")
def my_access(ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    """Catégories de documents accessibles (calculées côté serveur, même logique que l'outil MCP)."""
    from app.mcp.tools import get_user_permissions
    return get_user_permissions(db, ctx)
