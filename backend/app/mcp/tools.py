"""Logique des 3 outils MCP, indépendante du transport. L'identité (AuthContext) est TOUJOURS fournie par le serveur :
aucun argument d'outil ne peut porter un user_id/rôle/département (modèles pydantic `extra=forbid`).
Chaque outil ré-applique lui-même les permissions."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import log_access
from app.auth.deps import AuthContext
from app.config import get_settings
from app.database.models import Department, Document
from app.documents.service import active_version_number
from app.permissions.acl import accessible_documents_clause
from app.rag.embeddings import get_embedder
from app.rag.retrieval import search_chunks
from app.reranker.service import get_reranker

DeptCode = Literal["HR", "IT", "FINANCE", "POLICIES"]


class ToolError(Exception):
    """Erreur renvoyée au client/LLM : message volontairement générique (pas de fuite d'existence)."""


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    department: DeptCode | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class MetadataArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int = Field(ge=1)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def search_documents(db: Session, ctx: AuthContext, args: SearchArgs) -> dict:
    if "documents:read" not in ctx.permissions:
        log_access(db, action="mcp.search_documents", allowed=False, user_id=ctx.user.id, reason="missing_permission")
        raise ToolError("Permission denied")
    vec = get_embedder().embed([args.query])[0]
    hits = search_chunks(db, ctx.role_ids, vec, max(30, args.top_k), args.department,
                         get_settings().min_retrieval_score)
    scores = get_reranker(db).score(args.query, [h.content for h in hits])
    ranked = sorted(zip(hits, scores), key=lambda p: p[1], reverse=True)[: args.top_k]
    log_access(db, action="mcp.search_documents", allowed=True, user_id=ctx.user.id, reason=f"results={len(ranked)}")
    return {"results": [
        {"document_id": h.document_id, "chunk_id": h.chunk_id, "title": h.title, "department": h.department,
         "classification": h.classification, "version": h.version, "snippet": h.content[:400], "score": round(s, 4)}
        for h, s in ranked]}


def get_user_permissions(db: Session, ctx: AuthContext, args: NoArgs | None = None) -> dict:
    rows = db.execute(
        select(Department.code, Document.classification, func.count(Document.id))
        .join(Department, Document.department_id == Department.id)
        .where(accessible_documents_clause(set(ctx.role_ids)))
        .group_by(Department.code, Document.classification)).all()
    log_access(db, action="mcp.get_user_permissions", allowed=True, user_id=ctx.user.id)
    return {
        "roles": sorted(ctx.role_names),
        "department": ctx.user.department.code,
        "permissions": sorted(ctx.permissions),
        "accessible_document_categories": [
            {"department": d, "classification": c, "documents": n} for d, c, n in sorted(rows)],
        "restrictions": [
            "Only ACTIVE documents explicitly shared with your roles are accessible.",
            "Access is never granted by department alone.",
            "Archived, draft and deleted documents are never searchable.",
        ],
    }


def get_document_metadata(db: Session, ctx: AuthContext, args: MetadataArgs) -> dict:
    doc = db.scalar(select(Document).where(Document.id == args.document_id,
                                           accessible_documents_clause(set(ctx.role_ids))))
    if doc is None:  # inexistant OU non autorisé : même réponse
        log_access(db, action="mcp.get_document_metadata", allowed=False, user_id=ctx.user.id,
                   resource_type="document", resource_id=args.document_id, reason="not_found_or_forbidden")
        raise ToolError("Document not found")
    log_access(db, action="mcp.get_document_metadata", allowed=True, user_id=ctx.user.id,
               resource_type="document", resource_id=doc.id)
    dept = db.get(Department, doc.department_id)
    return {"document_id": doc.id, "title": doc.title, "department": dept.code, "classification": doc.classification,
            "current_version": active_version_number(db, doc.id), "status": doc.status,
            "created_at": doc.created_at.isoformat(), "updated_at": doc.updated_at.isoformat()}


TOOLS = {
    "search_documents": (SearchArgs, search_documents),
    "get_user_permissions": (NoArgs, get_user_permissions),
    "get_document_metadata": (MetadataArgs, get_document_metadata),
}


def execute_tool(db: Session, ctx: AuthContext, name: str, raw_args: dict) -> dict:
    """Utilisé par l'agent : valide strictement les arguments produits par le LLM puis exécute."""
    if name not in TOOLS:
        raise ToolError("Unknown tool")
    model, fn = TOOLS[name]
    try:
        args = model.model_validate(raw_args or {})
    except ValidationError:
        log_access(db, action=f"mcp.{name}", allowed=False, user_id=ctx.user.id, reason="invalid_arguments")
        raise ToolError("Invalid tool arguments")
    return fn(db, ctx, args)
