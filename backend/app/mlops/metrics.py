"""Métriques de ranking. Entrée : pour chaque requête, liste de (score_modèle, label_pertinence).
Les labels > 0 sont pertinents (gain = label). Aucune conclusion d'amélioration n'est tirée sans comparer les chiffres."""
import math
from typing import Sequence

Ranked = Sequence[tuple[float, float]]
KEYS = ("mrr@10", "ndcg@10", "recall@10", "precision@5")


def _order(cands: Ranked) -> list[float]:
    return [label for _, label in sorted(cands, key=lambda c: c[0], reverse=True)]  # tri stable : ex-aequo gardent l'ordre d'entrée


def mrr_at_k(cands: Ranked, k: int = 10) -> float:
    for i, label in enumerate(_order(cands)[:k], 1):
        if label > 0:
            return 1.0 / i
    return 0.0


def ndcg_at_k(cands: Ranked, k: int = 10) -> float:
    labels = _order(cands)
    dcg = sum((2 ** l - 1) / math.log2(i + 2) for i, l in enumerate(labels[:k]))
    ideal = sorted((l for _, l in cands), reverse=True)
    idcg = sum((2 ** l - 1) / math.log2(i + 2) for i, l in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(cands: Ranked, k: int = 10) -> float:
    total = sum(1 for _, l in cands if l > 0)
    return sum(1 for l in _order(cands)[:k] if l > 0) / total if total else 0.0


def precision_at_k(cands: Ranked, k: int = 5) -> float:
    return sum(1 for l in _order(cands)[:k] if l > 0) / k


def evaluate(queries: Sequence[Ranked]) -> dict[str, float]:
    qs = [q for q in queries if any(l > 0 for _, l in q)]  # requêtes sans positif exclues (non évaluables)
    if not qs:
        raise ValueError("no evaluable queries (no relevant candidate)")
    n = len(qs)
    return {
        "mrr@10": sum(mrr_at_k(q) for q in qs) / n,
        "ndcg@10": sum(ndcg_at_k(q) for q in qs) / n,
        "recall@10": sum(recall_at_k(q) for q in qs) / n,
        "precision@5": sum(precision_at_k(q) for q in qs) / n,
        "num_queries": n,
    }


def compare(baseline: dict, candidate: dict, tol: float = 1e-9) -> dict:
    delta = {k: candidate[k] - baseline[k] for k in KEYS}
    up = [k for k, v in delta.items() if v > tol]
    down = [k for k, v in delta.items() if v < -tol]
    verdict = "improved" if up and not down else "degraded" if down and not up else "mixed" if up and down else "unchanged"
    return {"delta": delta, "verdict": verdict}
