from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, TokenResponse
from app.audit.service import log_access
from app.auth.deps import AuthContext, get_auth_context
from app.config import get_settings
from app.database.models import RevokedToken, User
from app.database.session import get_db
from app.security.passwords import verify_password
from app.security.tokens import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    ok = verify_password(body.password, user.hashed_password if user else None)
    if not (user and ok and user.is_active):
        log_access(db, action="auth.login", allowed=False, user_id=user.id if user else None,
                   reason="bad_credentials_or_inactive", request=request)
        # même message dans tous les cas : pas d'énumération de comptes
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token, _, _ = create_access_token(user.id)
    log_access(db, action="auth.login", allowed=True, user_id=user.id, request=request)
    return TokenResponse(access_token=token, expires_in=get_settings().access_token_expire_minutes * 60)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)):
    from app.security.tokens import decode_access_token
    token = request.headers["authorization"].split(" ", 1)[1]
    exp = datetime.fromtimestamp(decode_access_token(token)["exp"])
    db.add(RevokedToken(jti=ctx.jti, expires_at=exp))
    db.commit()
    log_access(db, action="auth.logout", allowed=True, user_id=ctx.user.id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
