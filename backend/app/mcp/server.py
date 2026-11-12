"""Serveur MCP (SDK officiel `mcp`). Identité de confiance :
 - transport HTTP : en-tête Authorization: Bearer <JWT> de la requête ;
 - stdio : variable d'environnement MCP_ACCESS_TOKEN du processus serveur (jamais un argument d'outil).
Le JWT passe par la même authentification que l'API (signature, expiration, révocation, utilisateur actif)."""
import os

from mcp.server.fastmcp import Context, FastMCP

from app.auth.deps import authenticate_token
from app.database.session import SessionLocal
from app.mcp import tools as core

mcp = FastMCP("secure-enterprise-assistant",
              host=os.getenv("MCP_HOST", "127.0.0.1"), port=int(os.getenv("MCP_PORT", "8765")))


def _token(ctx: Context | None) -> str | None:
    try:
        req = ctx.request_context.request if ctx else None
        auth = req.headers.get("authorization", "") if req is not None else ""
        if auth.lower().startswith("bearer "):
            return auth[7:]
    except Exception:  # pas de requête HTTP (stdio)
        pass
    return os.getenv("MCP_ACCESS_TOKEN")


def _run(ctx: Context | None, fn, args):
    token = _token(ctx)
    if not token:
        raise ValueError("Authentication required")
    with SessionLocal() as db:
        try:
            auth = authenticate_token(db, token)
        except Exception:
            raise ValueError("Authentication failed")
        try:
            return fn(db, auth, args)
        except core.ToolError as exc:
            raise ValueError(str(exc))


@mcp.tool()
def search_documents(query: str, department: str | None = None, top_k: int = 5, ctx: Context = None) -> dict:
    """Search enterprise documents the authenticated user is authorized to read."""
    try:
        args = core.SearchArgs(query=query, department=department, top_k=top_k)
    except Exception:
        raise ValueError("Invalid arguments")
    return _run(ctx, core.search_documents, args)


@mcp.tool()
def get_user_permissions(ctx: Context = None) -> dict:
    """Return the authenticated user's role, department, accessible document categories and restrictions."""
    return _run(ctx, core.get_user_permissions, core.NoArgs())


@mcp.tool()
def get_document_metadata(document_id: int, ctx: Context = None) -> dict:
    """Return metadata of an authorized document (unauthorized ids behave like missing ones)."""
    try:
        args = core.MetadataArgs(document_id=document_id)
    except Exception:
        raise ValueError("Invalid arguments")
    return _run(ctx, core.get_document_metadata, args)


if __name__ == "__main__":
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))
