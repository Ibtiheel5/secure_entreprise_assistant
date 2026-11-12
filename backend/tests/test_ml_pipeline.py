"""Tests des fonctions pures du pipeline ML. Les lignes ci-dessous sont des FIXTURES de test qui imitent les schémas
documentés (elles ne sont pas des données du produit). Le téléchargement/entraînement réels ne sont pas exécutés ici."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from ml.datasets.common import check_no_leakage, write_jsonl  # noqa: E402
from ml.evaluation.evaluate_reranker import evaluate_scorer, group_pairs  # noqa: E402
from ml.preprocessing import cuad, enterprise_rag, msmarco, multidoc2dial  # noqa: E402
from ml.training.train_reranker import load_pairs  # noqa: E402


def ms_rows(n=60):
    return [{"query_id": i, "query": f"query {i}", "passages": {"is_selected": [1, 0, 0, 0],
             "passage_text": [f"relevant {i}", f"neg a {i}", f"neg b {i}", f"neg c {i}"]}} for i in range(n)]


def test_msmarco_pairs_sampling_kinds_and_no_leakage():
    pairs = msmarco.build_pairs(ms_rows(), n_queries=40, hard=2, easy=1)
    assert len({p["query_id"] for p in pairs}) == 40                       # échantillonnage configurable
    assert {p["kind"] for p in pairs} == {"positive", "hard_negative", "easy_negative"}
    check_no_leakage(pairs)
    assert pairs == msmarco.build_pairs(ms_rows(), n_queries=40, hard=2, easy=1)   # reproductible
    assert all(p["label"] == 1.0 for p in pairs if p["kind"] == "positive")


def test_msmarco_schema_mismatch_fails_loudly_and_bad_rows_skipped():
    with pytest.raises(KeyError, match="expected fields"):
        msmarco.build_pairs([{"foo": 1}])
    bad = [{"query_id": 1, "query": "q", "passages": {"is_selected": [1], "passage_text": ["a", "b"]}}]
    assert msmarco.build_pairs(bad) == []


def test_multidoc2dial_conversion():
    docs = list(multidoc2dial.convert_documents([{"doc_id": "d1", "title": "T", "domain": "dmv", "doc_text": "text"}]))
    assert docs[0]["doc_id"] == "md2d:d1" and docs[0]["department"] == "POLICIES"
    dial = [{"dial_id": "x", "turns": [{"role": "user", "utterance": "How do I renew?"},
            {"role": "agent", "utterance": "Visit the office.", "references": [{"doc_id": "d1"}]}]}]
    ev = list(multidoc2dial.convert_dialogues(dial))
    assert ev[0]["relevant_doc_ids"] == ["md2d:d1"] and ev[0]["answer"] == "Visit the office."
    with pytest.raises(KeyError):
        list(multidoc2dial.convert_documents([{"doc_id": "d"}]))


def test_cuad_contracts_not_classified_as_hr():
    rows = [{"id": "a1", "title": "ACME_Agreement", "context": "This agreement...", "question": "Governing law?",
             "answers": {"text": ["State of Delaware"], "answer_start": [10]}},
            {"id": "a2", "title": "ACME_Agreement", "context": "This agreement...", "question": "Audit rights?",
             "answers": {"text": [], "answer_start": []}}]
    docs, ev = cuad.convert(rows)
    assert len(docs) == 1 and docs[0]["department"] != "HR" and docs[0]["allowed_roles"] == ["CEO"]
    assert len(ev) == 1 and ev[0]["answer"] == "State of Delaware"


def test_enterprise_rag_requires_explicit_mapping_and_keeps_ids():
    m = {"doc_id": "id", "title": "name", "text": "body"}
    out = list(enterprise_rag.convert_docs([{"id": 7, "name": "N", "body": "B"}], m, ["CEO"]))
    assert out[0]["metadata"]["original_id"] == 7
    with pytest.raises(KeyError):
        list(enterprise_rag.convert_docs([{"x": 1}], m, ["CEO"]))


def test_load_pairs_split_filter_and_cap(tmp_path):
    p = tmp_path / "p.jsonl"
    write_jsonl(p, [{"split": "train", "i": i} for i in range(10)] + [{"split": "test", "i": 99}])
    assert len(load_pairs([p], {"train"})) == 10 and len(load_pairs([p], {"train"}, 3)) == 3
    assert all(r["split"] == "test" for r in load_pairs([p], {"test"}))


def test_evaluate_scorer_baseline_vs_better_model_and_verdict():
    from app.mlops.metrics import compare
    rows = []
    for q in range(5):
        for k, label in enumerate([1.0, 0.0, 0.0, 0.0]):
            rows.append({"query_id": f"q{q}", "query": "q", "passage": f"{'good' if label else 'bad'}{k}", "label": label})
    groups = group_pairs(rows)
    bad = lambda pairs: [0.9 if p.startswith("bad1") else 0.1 for _, p in pairs]
    good = lambda pairs: [1.0 if p.startswith("good") else 0.0 for _, p in pairs]
    b, g = evaluate_scorer(groups, bad), evaluate_scorer(groups, good)
    assert g["mrr@10"] == 1.0 and b["mrr@10"] < 1.0
    assert compare(b, g)["verdict"] == "improved" and compare(g, b)["verdict"] == "degraded"
