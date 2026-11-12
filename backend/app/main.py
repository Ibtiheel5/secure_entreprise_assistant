import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import admin, auth, chat, documents, security_ml, users
from app.config import get_settings
from app.database.session import engine

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("api")

app = FastAPI(title="Secure Enterprise Knowledge Assistant", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    # on journalise méthode/chemin/statut/durée, jamais d'en-têtes ni de corps (tokens, mots de passe)
    log.info("%s %s %s %.1fms", request.method, request.url.path, response.status_code,
             (time.perf_counter() - start) * 1000)
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(security_ml.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
