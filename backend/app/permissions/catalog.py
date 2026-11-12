"""Catalogue des permissions et des rôles (source de vérité du seed)."""

PERMISSIONS = {
    "chat:use": "Use the AI assistant",
    "documents:read": "Search/read documents (still subject to document ACL)",
    "documents:write": "Upload documents and new versions",
    "documents:manage_permissions": "Change document ACLs and lifecycle",
    "users:read": "List users",
    "users:manage": "Create and modify users",
    "security:view": "View security dashboard and audit logs",
    "ml:view": "View MLOps dashboard",
    "ml:manage": "Deploy reranker versions",
}

_STAFF = ["chat:use", "documents:read"]
_MANAGER = _STAFF + ["documents:write"]

ROLES: dict[str, tuple[str, list[str]]] = {
    "CEO": ("Executive access", _STAFF + ["users:read", "security:view", "ml:view"]),
    "HR_MANAGER": ("HR manager", _MANAGER),
    "HR_EMPLOYEE": ("HR employee", _STAFF),
    "IT_MANAGER": ("IT manager", _MANAGER + ["ml:view"]),
    "IT_EMPLOYEE": ("IT employee", _STAFF),
    "FINANCE_MANAGER": ("Finance manager", _MANAGER),
    "FINANCE_EMPLOYEE": ("Finance employee", _STAFF),
    "GENERAL_EMPLOYEE": ("General employee", _STAFF),
    "SYSTEM_ADMIN": (
        "Platform administrator (manages users/ACLs; reads documents only if listed in their ACL)",
        ["documents:write", "documents:manage_permissions", "users:read", "users:manage",
         "security:view", "ml:view", "ml:manage"],
    ),
}

DEPARTMENTS = {
    "HR": "Human Resources",
    "IT": "Information Technology",
    "FINANCE": "Finance",
    "POLICIES": "General Company Policies",
}
