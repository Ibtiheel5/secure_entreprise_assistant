import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.audit.service import log_access
from app.auth.deps import AuthContext, require_permission
from app.config import get_settings
from app.database.models import AccessLog, Department, ModelExperiment, User
from app.database.session import get_db
from app.reranker.service import resolve_model_path

router = APIRouter(prefix="/api", tags=["security", "mlops"])


@router.get("/security/overview")
def overview(ctx: AuthContext = Depends(require_permission("security:view")), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(AccessLog.id))) or 0
    allowed = db.scalar(select(func.count(AccessLog.id)).where(AccessLog.allowed.is_(True))) or 0
    count = lambda *w: db.scalar(select(func.count(AccessLog.id)).where(*w)) or 0
    by_dept = db.execute(
        select(Department.code, func.count(AccessLog.id),
               func.sum(case((AccessLog.allowed.is_(False), 1), else_=0)))
        .join(User, User.department_id == Department.id).join(AccessLog, AccessLog.user_id == User.id)
        .group_by(Department.code)).all()
    report_path = Path(get_settings().security_report_path)
    tests = json.loads(report_path.read_text()) if report_path.exists() else None
    return {
        "total_access_attempts": total, "authorized_requests": allowed, "denied_requests": total - allowed,
        "auth_failures": count(AccessLog.action.like("auth.%"), AccessLog.allowed.is_(False)),
        "unauthorized_document_attempts": count(AccessLog.resource_type == "document", AccessLog.allowed.is_(False)),
        "prompt_injection_suspected": count(AccessLog.action == "chat.prompt_injection_suspected"),
        "by_department": [{"department": d, "requests": n, "denied": int(x or 0)} for d, n, x in by_dept],
        "security_tests": tests,  # None tant que scripts/run_security_suite.py n'a pas été exécuté
    }


@router.get("/security/audit-logs")
def audit_logs(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), denied_only: bool = False,
               ctx: AuthContext = Depends(require_permission("security:view")), db: Session = Depends(get_db)):
    where = [AccessLog.allowed.is_(False)] if denied_only else []
    total = db.scalar(select(func.count(AccessLog.id)).where(*where)) or 0
    rows = db.scalars(select(AccessLog).where(*where).order_by(AccessLog.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": r.id, "user_id": r.user_id, "action": r.action, "resource_type": r.resource_type,
         "resource_id": r.resource_id, "allowed": r.allowed, "reason": r.reason, "ip": r.ip_address,
         "created_at": r.created_at.isoformat()} for r in rows]}


def _exp(e: ModelExperiment) -> dict:
    return {"id": e.id, "run_id": e.mlflow_run_id, "model_name": e.model_name, "version": e.version,
            "params": e.params, "metrics": e.metrics, "is_deployed": e.is_deployed,
            "created_at": e.created_at.isoformat()}


@router.get("/ml/experiments")
def experiments(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                ctx: AuthContext = Depends(require_permission("ml:view")), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(ModelExperiment.id))) or 0
    rows = db.scalars(select(ModelExperiment).order_by(ModelExperiment.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "items": [_exp(e) for e in rows]}


@router.get("/ml/models")
def models(ctx: AuthContext = Depends(require_permission("ml:view")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelExperiment).order_by(ModelExperiment.id.desc())).all()
    return {"serving_model": resolve_model_path(db), "versions": [_exp(e) for e in rows]}


@router.get("/ml/evaluation")
def evaluation(ctx: AuthContext = Depends(require_permission("ml:view")), db: Session = Depends(get_db)):
    """Comparaison des métriques par version ; la conclusion « amélioration » n'est tirée que des chiffres stockés."""
    rows = db.scalars(select(ModelExperiment).where(ModelExperiment.metrics.is_not(None))
                      .order_by(ModelExperiment.id)).all()
    base = next((e for e in rows if e.version == "baseline"), None)
    out = []
    for e in rows:
        delta = None
        if base and e is not base:
            delta = {k: round(v - base.metrics[k], 4) for k, v in e.metrics.items()
                     if k in base.metrics and isinstance(v, (int, float))}
        out.append({**_exp(e), "delta_vs_baseline": delta})
    return {"baseline_available": base is not None, "models": out}


@router.post("/ml/models/{exp_id}/deploy")
def deploy(exp_id: int, request: Request, ctx: AuthContext = Depends(require_permission("ml:manage")),
           db: Session = Depends(get_db)):
    e = db.get(ModelExperiment, exp_id)
    if e is None or not (e.params or {}).get("model_path"):
        raise HTTPException(404, "Model version not found or has no model_path")
    for o in db.scalars(select(ModelExperiment).where(ModelExperiment.is_deployed.is_(True))):
        o.is_deployed = False
    e.is_deployed = True
    db.commit()
    log_access(db, action="ml.deploy", allowed=True, user_id=ctx.user.id, resource_type="model",
               resource_id=e.id, request=request)
    return _exp(e)
