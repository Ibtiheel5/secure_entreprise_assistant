# Secure Enterprise Knowledge Assistant

Enterprise RAG platform with **role-based and document-level access control enforced inside the retrieval query**, a real MCP server
(3 tools), a cross-encoder reranker pipeline (fine-tuning + evaluation + MLflow), audit logging, security tests and a React dashboard.
All company data in this repo is fictional ("Nordia Systems").

## What is verified vs. not (read this first)

| Area | Status |
|---|---|
| Auth (Argon2, JWT, logout/revocation), RBAC, document ACL, versioning, lifecycle | ✅ implemented, **92 pytest tests pass** (SQLite) |
| Secure RAG: ACL-in-query retrieval, reranking hook, prompt construction, citation validation, refusals | ✅ tested with a deterministic hash embedder + scripted LLM |
| 10 adversarial scenarios + "no leak in results / reranker / LLM context / citations / MCP" | ✅ 17/17 security tests (`docs/security/SECURITY_REPORT.md`) |
| MCP server (official SDK `mcp<2`): 3 tools, server-side identity | ✅ tested in-process; stdio/HTTP transports not exercised over the network |
| Frontend (7 pages) | ✅ type-checks and builds; ⚠️ not run in a browser against a live stack |
| Live API smoke test (seed → ingest synthetic corpus → login → ACL listing → 404 on forbidden doc) | ✅ on SQLite |
| PostgreSQL + pgvector path (`<=>` ordering, HNSW index, Alembic migration) | ⚠️ **not executed** (no Postgres in the build env); migration validated on SQLite only |
| Docker Compose | ⚠️ **written but never started** (no Docker in the build env) |
| Real embeddings (`sentence-transformers`), real LLM (Ollama) | ⚠️ code paths implemented, **not run** |
| External datasets (EnterpriseRAG-Bench, MultiDoc2Dial, MS MARCO, CUAD) | ⚠️ scripts only; **nothing downloaded/verified** (no Hugging Face access). EnterpriseRAG-Bench repository **unconfirmed** |
| Reranker fine-tuning, baseline vs fine-tuned comparison, MLflow runs | ❌ **not run → no results and no improvement claimed** (`docs/evaluation/EVALUATION.md`) |

## Quick start (Docker)
```bash
cp .env.example .env     # set JWT_SECRET, POSTGRES_PASSWORD, SEED_PASSWORD, LLM/embedding options
docker compose up --build -d                       # db, backend (runs alembic), frontend :5173, mlflow :5000, mcp :8765
docker compose exec backend python -m app.database.seed
# load the synthetic corpus from the host (DATABASE_URL pointing to localhost:5432, same embedding settings as the backend):
python scripts/ingest_corpus.py --docs data/synthetic/docs.jsonl --relevance data/processed/synthetic_pairs.jsonl
# optional local LLM:
docker compose --profile ollama up -d && docker compose exec ollama ollama pull llama3.2:3b
```
Limited RAM / offline demo: set `EMBEDDING_BACKEND=hash`, `RERANKER_BACKEND=none` (lexical matching only, **no semantics**) and a small `OLLAMA_MODEL`.
For real embeddings build with `INSTALL_AI=true`. No model is downloaded at image build time; models download on first use into the `models` volume.

## Local development (no Docker, SQLite)
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
export DATABASE_URL=sqlite:///./dev.db JWT_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
       SEED_PASSWORD='Change-Me-12345' EMBEDDING_BACKEND=hash RERANKER_BACKEND=none PYTHONPATH=..:.
python -c "from app.database import models; from app.database.session import Base, engine; Base.metadata.create_all(engine)"
python -m app.database.seed
python ../scripts/ingest_corpus.py --docs ../data/synthetic/docs.jsonl --relevance ../data/processed/synthetic_pairs.jsonl
uvicorn app.main:app --reload            # API on :8000 ; in another shell: cd ../frontend && npm install && npm run dev
```
Demo users (`@nordia-demo.com`, password = `SEED_PASSWORD`): admin, ceo, hr.manager, hr.employee, it.manager, it.employee, finance.manager, finance.employee, employee.

## Tests
```bash
cd backend && pytest -q                     # 92 tests
python ../scripts/run_security_suite.py     # security subset -> docs/security/SECURITY_REPORT.md + security_report.json (feeds the Security dashboard)
```

## MCP server
Tools: `search_documents(query, department?, top_k?)`, `get_user_permissions()`, `get_document_metadata(document_id)`.
```bash
# stdio (identity = JWT in the server-process env)
MCP_ACCESS_TOKEN=<jwt> python -m app.mcp.server
# HTTP (identity = Authorization: Bearer <jwt> on every request) – the compose service `mcp`
```
Tools take **no** user/role arguments; unauthorized document ids behave exactly like missing ones.

## Repository layout
`backend/app/{api,auth,permissions,documents,rag,reranker,agents,mcp,mlops,audit,security,database}` · `backend/tests` ·
`frontend/` (React+TS+Tailwind+Recharts) · `ml/{datasets,preprocessing,training,evaluation,mlops}` · `data/{HR,IT,Finance,Policies,synthetic,processed}` ·
`scripts/` · `docs/{architecture,api,security,datasets,evaluation}`.

## Documentation
[Architecture + ER diagram](docs/architecture/ARCHITECTURE.md) · [API](docs/api/API.md) · [Security design](docs/security/SECURITY.md) ·
[Security report](docs/security/SECURITY_REPORT.md) · [Datasets & licenses](docs/datasets/DATASETS.md) · [Evaluation](docs/evaluation/EVALUATION.md)

## Known limitations
No login rate limiting; token kept in `sessionStorage`; chat responses are not streamed; scanned PDFs (no OCR) are rejected;
"semantic" chunking is structure-aware (paragraph/sentence), not embedding-based; `MIN_RETRIEVAL_SCORE` is uncalibrated;
the agent calls the MCP tool layer in-process rather than over an MCP transport.
