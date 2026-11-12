import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


class TokenError(Exception):
    pass


def create_access_token(user_id: int) -> tuple[str, str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.access_token_expire_minutes)
    jti = uuid.uuid4().hex
    token = jwt.encode(
        {"sub": str(user_id), "jti": jti, "iat": now, "exp": exp},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    return token, jti, exp


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],  # liste fixe : refuse alg=none et la confusion d'algorithme
            options={"require": ["exp", "sub", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
