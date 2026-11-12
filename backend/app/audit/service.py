import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.database.models import AccessLog

logger = logging.getLogger("audit")


def log_access(
    db: Session,
    *,
    action: str,
    allowed: bool,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    reason: str | None = None,
    request: Request | None = None,
) -> None:
    """Journal d'audit. Ne jamais y mettre de mot de passe, de token ou de contenu de document."""
    ip = request.client.host if request and request.client else None
    db.add(AccessLog(
        user_id=user_id, action=action, allowed=allowed, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        reason=reason, ip_address=ip,
    ))
    db.commit()
    logger.info("access action=%s allowed=%s user=%s resource=%s/%s",
                action, allowed, user_id, resource_type, resource_id)
