from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.audit.service import log_access
from app.database.models import RevokedToken, User
from app.database.session import get_db
from app.security.tokens import TokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """Identité de confiance, reconstruite côté serveur à CHAQUE requête depuis la base.
    Rien (rôle, département, id) n'est lu depuis le frontend ni depuis les claims du JWT, sauf `sub`/`jti`."""
    user: User
    jti: str
    role_ids: frozenset[int] = field(default_factory=frozenset)
    role_names: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                         headers={"WWW-Authenticate": "Bearer"})


def authenticate_token(db: Session, token: str, request: Request | None = None) -> AuthContext:
    """Point d'entrée unique d'authentification (API HTTP et serveur MCP)."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (TokenError, ValueError):
        log_access(db, action="auth.token", allowed=False, reason="invalid_token", request=request)
        raise _unauthorized()

    if db.get(RevokedToken, payload["jti"]):
        log_access(db, action="auth.token", allowed=False, user_id=user_id,
                   reason="revoked_token", request=request)
        raise _unauthorized()

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        log_access(db, action="auth.token", allowed=False, user_id=user_id,
                   reason="unknown_or_inactive_user", request=request)
        raise _unauthorized()

    return AuthContext(
        user=user,
        jti=payload["jti"],
        role_ids=frozenset(r.id for r in user.roles),
        role_names=frozenset(r.name for r in user.roles),
        permissions=frozenset(p.code for r in user.roles for p in r.permissions),
    )


def get_auth_context(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    if creds is None:
        raise _unauthorized()
    return authenticate_token(db, creds.credentials, request)


def require_permission(code: str):
    def dependency(
        request: Request,
        ctx: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> AuthContext:
        if code not in ctx.permissions:
            log_access(db, action=f"permission:{code}", allowed=False, user_id=ctx.user.id,
                       resource_type="endpoint", resource_id=request.url.path,
                       reason="missing_permission", request=request)
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
        return ctx

    return dependency
