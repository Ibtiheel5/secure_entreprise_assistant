"""Évaluation baseline vs fine-tuné sur le split TEST (jamais vu à l'entraînement) + enregistrement MLflow/DB.
  python -m ml.evaluation.evaluate_reranker --test data/processed/msmarco_pairs.jsonl data/processed/synthetic_pairs.jsonl \
      --finetuned ml/models/ft-1 [--register-db] [--mlflow]
Le verdict (improved/degraded/mixed/unchanged) est calculé à partir des chiffres ; aucune amélioration n'est supposée."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from app.mlops.metrics import compare, evaluate
from ml.datasets.common import file_sha256, read_jsonl


def group_pairs(rows) -> dict[str, list[tuple[str, str, float]]]:
    g = defaultdict(list)
    for r in rows:
        g[r["query_id"]].append((r["query"], r["passage"], r["label"]))
    return g


def evaluate_scorer(groups, score_fn) -> dict:
    """score_fn(list[(query, passage)]) -> list[float]. Fonction pure testable avec un faux scorer."""
    ranked = []
    for items in groups.values():
        scores = score_fn([(q, p) for q, p, _ in items])
        ranked.append([(s, l) for s, (_, _, l) in zip(scores, items)])
    return evaluate(ranked)


def transformers_scorer(model_path: str, max_len=256, batch_size=32, device="auto"):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    dev = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
    tok = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path).to(dev).eval()

    def score(pairs):
        out = []
        with torch.no_grad():
            for i in range(0, len(pairs), batch_size):
                chunk = pairs[i:i + batch_size]
                enc = tok([q for q, _ in chunk], [p for _, p in chunk], truncation=True, max_length=max_len,
                          padding=True, return_tensors="pt").to(dev)
                out += model(**enc).logits.squeeze(-1).tolist()
        return out
    return score


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--baseline", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    ap.add_argument("--finetuned", required=True)
    ap.add_argument("--out", default="docs/evaluation/reranker_eval.json")
    ap.add_argument("--max-queries", type=int)
    ap.add_argument("--register-db", action="store_true")
    ap.add_argument("--mlflow", action="store_true")
    a = ap.parse_args(argv)

    groups = group_pairs(r for p in a.test for r in read_jsonl(p) if r.get("split") == "test")
    if a.max_queries:
        groups = dict(list(groups.items())[: a.max_queries])
    if not groups:
        raise SystemExit("No test queries found (split == 'test')")
    base = evaluate_scorer(groups, transformers_scorer(a.baseline))
    ft = evaluate_scorer(groups, transformers_scorer(a.finetuned))
    cmp = compare(base, ft)
    report = {"test_queries": len(groups), "test_files_sha256": [file_sha256(p)[:16] for p in a.test],
              "baseline": {"model": a.baseline, **base}, "finetuned": {"model": a.finetuned, **ft}, **cmp}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    run_id = None
    if a.mlflow:
        from ml.mlops.mlflow_utils import log_metrics, tracked_run
        with tracked_run("reranker-evaluation", "baseline-vs-finetuned", {"baseline": a.baseline, "finetuned": a.finetuned}) as run:
            log_metrics({f"baseline_{k}": v for k, v in base.items()}); log_metrics({f"finetuned_{k}": v for k, v in ft.items()})
            run_id = run.info.run_id
    if a.register_db:
        from app.database.session import SessionLocal
        from app.mlops.tracking import register_experiment
        with SessionLocal() as db:
            register_experiment(db, model_name=a.baseline, version="baseline", params={"model_path": a.baseline},
                                metrics=base)
            n = register_experiment(db, model_name=a.baseline, version=Path(a.finetuned).name,
                                    params={"model_path": str(Path(a.finetuned).resolve()), "verdict": cmp["verdict"]},
                                    metrics=ft, mlflow_run_id=run_id)
            print(f"registered experiment id={n.id} (deploy it from the MLOps dashboard / POST /api/ml/models/{n.id}/deploy)")


if __name__ == "__main__":
    main()
