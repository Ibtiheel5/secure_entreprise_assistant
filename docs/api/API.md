# API reference

Generated from the FastAPI OpenAPI schema (`/docs` serves the interactive version). All endpoints except `/api/auth/login` and `/health*` require `Authorization: Bearer <JWT>`. Identity, role and department are always derived server-side.

| Method | Path | Summary / required permission |
|---|---|---|
| GET | `/api/admin/documents` | documents:manage_permissions |
| GET | `/api/admin/roles` | users:manage |
| GET | `/api/admin/stats` | users:manage |
| PUT | `/api/admin/users/{user_id}/roles` | users:manage |
| POST | `/api/agent/chat` | chat:use |
| POST | `/api/auth/login` | public |
| POST | `/api/auth/logout` | authenticated |
| GET | `/api/auth/me` |  |
| POST | `/api/chat` | chat:use |
| GET | `/api/chat/sessions` | chat:use |
| GET | `/api/chat/sessions/{sid}` | chat:use |
| GET | `/api/documents` | documents:read |
| POST | `/api/documents/upload` | documents:write |
| GET | `/api/documents/{doc_id}` | documents:read |
| PUT | `/api/documents/{doc_id}/permissions` | documents:manage_permissions |
| PUT | `/api/documents/{doc_id}/status` | documents:manage_permissions |
| GET | `/api/documents/{doc_id}/versions` | documents:read |
| POST | `/api/documents/{doc_id}/versions` | documents:write |
| GET | `/api/ml/evaluation` | ml:view |
| GET | `/api/ml/experiments` | ml:view |
| GET | `/api/ml/models` | ml:view |
| POST | `/api/ml/models/{exp_id}/deploy` | ml:manage |
| GET | `/api/security/audit-logs` | security:view |
| GET | `/api/security/overview` | security:view |
| GET | `/api/users` | users:read |
| POST | `/api/users` | users:manage |
| GET | `/api/users/me` | authenticated |
| GET | `/api/users/me/access` | authenticated |
| GET | `/health` |  |
| GET | `/health/db` |  |
