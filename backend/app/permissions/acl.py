"""ACL au niveau document. Règle unique et deny-by-default :
un document est accessible ssi il est ACTIVE **et** l'un des rôles de l'utilisateur figure dans
document_permissions. Le département n'accorde jamais d'accès à lui seul.

`accessible_documents_clause` est le filtre SQL à injecter DANS la requête de retrieval (phase 4),
pour qu'un chunk non autorisé ne soit jamais lu, ni classé, ni envoyé au LLM.
"""
from sqlalchemy import exists, select

from app.database.models import Document, DocumentPermission, DocumentStatus


def can_access_document(role_ids: set[int], doc_status: str, allowed_role_ids: set[int]) -> bool:
    return doc_status == DocumentStatus.ACTIVE and bool(role_ids & allowed_role_ids)


def accessible_documents_clause(role_ids: set[int]):
    if not role_ids:
        return Document.id.is_(None)  # aucune ligne
    return (Document.status == DocumentStatus.ACTIVE) & exists(
        select(1).where(
            DocumentPermission.document_id == Document.id,
            DocumentPermission.role_id.in_(role_ids),
        )
    )
