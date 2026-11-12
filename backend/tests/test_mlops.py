import math

import pytest

from app.database.models import ModelExperiment
from app.mlops import metrics as M
from app.mlops.tracking import register_experiment
from app.reranker import service as rr


def test_metrics_known_values():
    perfect = [(0.9, 1), (0.5, 0), (0.1, 0)]
    worst = [(0.1, 1), (0.5, 0), (0.9, 0)]
    assert M.mrr_at_k(perfect) == 1.0 and M.mrr_at_k(worst) == pytest.approx(1 / 3)
    assert M.ndcg_at_k(perfect) == 1.0 and M.ndcg_at_k(worst) == pytest.approx(1 / math.log2(4))
    assert M.recall_at_k(worst, k=2) == 0.0 and M.recall_at_k(worst, k=3) == 1.0
    assert M.precision_at_k(perfect, k=5) == pytest.approx(1 / 5)
    assert M.mrr_at_k([(1, 0), (0.5, 0)]) == 0.0 and M.ndcg_at_k([(1, 0)]) == 0.0


def test_evaluate_excludes_queries_without_positive():
    r = M.evaluate([[(0.9, 1), (0.1, 0)], [(0.9, 0), (0.1, 0)]])
    assert r["num_queries"] == 1 and r["mrr@10"] == 1.0
    with pytest.raises(ValueError):
        M.evaluate([[(1, 0)]])


def test_compare_never_claims_improvement_without_numbers():
    base = {"mrr@10": .5, "ndcg@10": .5, "recall@10": .5, "precision@5": .5}
    assert M.compare(base, dict(base))["verdict"] == "unchanged"
    assert M.compare(base, {**base, "mrr@10": .6})["verdict"] == "improved"
    assert M.compare(base, {**base, "mrr@10": .4})["verdict"] == "degraded"
    assert M.compare(base, {**base, "mrr@10": .6, "ndcg@10": .4})["verdict"] == "mixed"


def test_ml_endpoints_real_data_and_deploy_flow(client, auth, db):
    base = {"mrr@10": .5, "ndcg@10": .55, "recall@10": .8, "precision@5": .3}
    register_experiment(db, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", version="baseline",
                        params={"model_path": "cross-encoder/ms-marco-MiniLM-L-6-v2"}, metrics=base)
    ft = register_experiment(db, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", version="ft-1",
                             params={"model_path": "/models/ft-1", "epochs": 2}, metrics={**base, "mrr@10": .62})
    ev = client.get("/api/ml/evaluation", headers=auth("ceo")).json()
    assert ev["baseline_available"]
    row = next(m for m in ev["models"] if m["version"] == "ft-1")
    assert row["delta_vs_baseline"]["mrr@10"] == pytest.approx(0.12)
    assert client.get("/api/ml/models", headers=auth("employee")).status_code == 403
    assert client.post(f"/api/ml/models/{ft.id}/deploy", headers=auth("ceo")).status_code == 403
    assert client.post(f"/api/ml/models/{ft.id}/deploy", headers=auth("admin")).status_code == 200
    m = client.get("/api/ml/models", headers=auth("ceo")).json()
    assert m["serving_model"] == "/models/ft-1"
    assert [v["version"] for v in m["versions"] if v["is_deployed"]] == ["ft-1"]
    assert client.post("/api/ml/models/9999/deploy", headers=auth("admin")).status_code == 404
    db.query(ModelExperiment).delete(); db.commit()
    assert rr.resolve_model_path(db) == "cross-encoder/ms-marco-MiniLM-L-6-v2"
