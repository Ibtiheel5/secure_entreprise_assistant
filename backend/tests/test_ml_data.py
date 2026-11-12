"""Tests du pipeline de données : corpus synthétique, exemples de pertinence, splits sans fuite, ingestion."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from ml.datasets.common import assign_splits, check_no_leakage, dedupe, split_of  # noqa: E402
from ml.datasets.synthetic.generate import build  # noqa: E402
from ml.datasets.synthetic.make_relevance import make_examples  # noqa: E402


def test_synthetic_corpus_schema_and_facts():
    rows = build()
    required = {"doc_id", "title", "department", "classification", "allowed_roles", "version", "status", "created_at", "updated_at"}
    assert all(required <= set(r) for r in rows)
    assert {r["department"] for r in rows} == {"HR", "IT", "FINANCE", "POLICIES"}
    for r in rows:
        for f in r["facts"]:
            assert f["answer"] in r["text"], (r["doc_id"], f)
    ids = [r["doc_id"] for r in rows]
    assert any(ids.count(i) > 1 for i in ids)                       # plusieurs versions
    for i in set(ids):                                               # au plus une version ACTIVE par document
        assert sum(r["status"] == "ACTIVE" for r in rows if r["doc_id"] == i) <= 1
    assert "6200 dinars" in next(r for r in rows if r["doc_id"] == "HR-SALARY")["text"]


def test_relevance_examples_have_all_kinds_and_no_leakage():
    ex = make_examples(build())
    assert {e["kind"] for e in ex} == {"positive", "hard_negative", "easy_negative"}
    assert {e["split"] for e in ex} == {"train", "val", "test"}
    check_no_leakage(ex)
    assert not {e["doc_id"] for e in ex if e["split"] == "test"} & {e["doc_id"] for e in ex if e["split"] == "train"}
    for e in ex:                                                       # un positif contient sa réponse, un négatif non
        fact = next(f for r in build() if r["doc_id"] == e["doc_id"] and r["status"] == "ACTIVE" for f in r["facts"] if f["question"] == e["query"])
        assert (fact["answer"] in e["passage"]) == (e["label"] == 1.0)


def test_only_active_versions_feed_relevance_examples():
    ex = make_examples(build())
    assert not any("receive 25 days" in e["passage"] for e in ex)     # v1 archivée exclue


def test_split_helpers():
    assert split_of("a") == split_of("a")
    s = assign_splits([f"k{i}" for i in range(10)])
    assert set(s.values()) == {"train", "val", "test"}
    with pytest.raises(ValueError):
        assign_splits(["a", "b"])
    with pytest.raises(ValueError):
        check_no_leakage([{"query_id": "q", "split": "train"}, {"query_id": "q", "split": "test"}])
    assert len(list(dedupe([{"a": 1}, {"a": 1}, {"a": 2}], ("a",)))) == 2


def test_ingestion_script_end_to_end(db, client, auth):
    sys.path.insert(0, str(ROOT / "scripts"))
    from ingest_corpus import ingest_docs
    from sqlalchemy import select
    from app.database.models import Document
    rows = [dict(r, doc_id="ING-" + r["doc_id"]) for r in build()]
    res = ingest_docs(db, rows)
    assert res["documents_created"] == 16
    assert ingest_docs(db, rows)["documents_skipped"] == 16          # idempotent
    status = {d.external_id: d.status for d in db.scalars(select(Document).where(Document.external_id.like("ING-%")))}
    assert status["ING-HR-LEAVE"] == "ACTIVE" and status["ING-POL-DRAFT"] == "DRAFT"
    leave = db.scalar(select(Document).where(Document.external_id == "ING-HR-LEAVE"))
    assert sorted((v.version_number, v.status) for v in leave.versions) == [(1, "ARCHIVED"), (2, "ACTIVE")]
    for d in db.scalars(select(Document).where(Document.external_id.like("ING-%"))).all():  # isolation des autres tests
        db.delete(d)
    db.commit()
