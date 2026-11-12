#!/usr/bin/env python
"""Ingère un docs.jsonl (format interne) dans PostgreSQL : documents, versions, chunks, embeddings, ACL.
  python scripts/ingest_corpus.py --docs data/synthetic/docs.jsonl [--relevance data/processed/synthetic_pairs.jsonl]
Nécessite DATABASE_URL/JWT_SECRET (voir .env) et le modèle d'embedding configuré (EMBEDDING_BACKEND)."""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "backend")]

from sqlalchemy import select  # noqa: E402

from app.database.models import Document, RelevanceExample  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.documents import service  # noqa: E402
from ml.datasets.common import read_jsonl  # noqa: E402


def ingest_docs(db, rows: list[dict]) -> dict:
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc_id"]].append(r)
    created = skipped = 0
    for doc_id, versions in by_doc.items():
        if db.scalar(select(Document).where(Document.external_id == doc_id)):
            skipped += 1  # idempotent : un document déjà ingéré n'est pas dupliqué
            continue
        versions.sort(key=lambda v: v["version"])
        first = versions[0]
        doc = service.create_document(
            db, title=first["title"], department_code=first["department"], classification=first["classification"],
            role_names=first["allowed_roles"], created_by=None, source=first.get("source", "synthetic"), external_id=doc_id)
        for v in versions:
            service.add_version_from_text(db, doc, text=v["text"], activate=v["status"] in ("ACTIVE", "ARCHIVED"))
        final = versions[-1]["status"]
        if final != "ACTIVE":
            if final == "DRAFT":
                db.commit()
            else:
                service.set_status(db, doc, final)
        created += 1
    return {"documents_created": created, "documents_skipped": skipped}


def ingest_relevance(db, rows: list[dict]) -> int:
    db.query(RelevanceExample).filter(RelevanceExample.source == "synthetic").delete()
    db.add_all(RelevanceExample(query=r["query"], passage=r["passage"], label=r["label"], split=r["split"],
                                source=r["source"]) for r in rows)
    db.commit()
    return len(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--relevance")
    a = ap.parse_args()
    with SessionLocal() as db:
        print(ingest_docs(db, list(read_jsonl(a.docs))))
        if a.relevance:
            print("relevance examples:", ingest_relevance(db, list(read_jsonl(a.relevance))))
