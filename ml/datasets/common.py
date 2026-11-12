"""Format interne unifié + utilitaires (JSONL, déduplication, split reproductible sans fuite, statistiques)."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator

# docs.jsonl   : {doc_id, title, text, source, department?, classification?, allowed_roles?, version?, status?, metadata?}
# eval.jsonl   : {query_id, query, relevant_doc_ids, answer?, source}
# pairs.jsonl  : {query_id, query, passage, label, kind, source, split?}   (kind: positive|hard_negative|easy_negative)


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); n += 1
    return n


def read_jsonl(path: str | Path) -> Iterator[dict]:
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def require_fields(row: dict, fields: Iterable[str], where: str) -> None:
    missing = [f for f in fields if f not in row]
    if missing:
        raise KeyError(f"{where}: expected fields {missing} not found; actual fields = {sorted(row)}. "
                       "Inspect the dataset (ml/datasets/inspect_dataset.py) and adapt the preprocessing.")


def split_of(key: str, ratios=(0.8, 0.1, 0.1), seed: int = 13) -> str:
    """Split déterministe par clé de GROUPE (requête/document) : toutes les lignes d'une même clé vont dans le même split."""
    h = int(hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "train" if h < ratios[0] else "val" if h < ratios[0] + ratios[1] else "test"


def assign_splits(keys: Iterable[str], ratios=(0.6, 0.2, 0.2), seed: int = 13) -> dict[str, str]:
    """Split par groupe GARANTISSANT des splits non vides (utile pour de petits corpus) : tri par hash puis découpage."""
    ks = sorted(set(keys), key=lambda k: hashlib.sha256(f"{seed}:{k}".encode()).hexdigest())
    n = len(ks)
    if n < 3:
        raise ValueError("need at least 3 groups to build train/val/test")
    n_val = max(1, round(n * ratios[1])); n_test = max(1, round(n * ratios[2]))
    out = {}
    for i, k in enumerate(ks):
        out[k] = "test" if i < n_test else "val" if i < n_test + n_val else "train"
    return out


def dedupe(rows: Iterable[dict], key_fields: tuple[str, ...]) -> Iterator[dict]:
    seen = set()
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        if k not in seen:
            seen.add(k)
            yield r


def check_no_leakage(rows: Iterable[dict], group_field: str = "query_id") -> None:
    groups: dict[str, set] = {}
    for r in rows:
        groups.setdefault(r[group_field], set()).add(r["split"])
    bad = [g for g, s in groups.items() if len(s) > 1]
    if bad:
        raise ValueError(f"leakage: {len(bad)} groups appear in several splits (e.g. {bad[:3]})")


def stats(rows: Iterable[dict], fields: tuple[str, ...] = ("split", "kind", "source", "label")) -> dict:
    rows = list(rows)
    return {"rows": len(rows), **{f: dict(Counter(str(r.get(f)) for r in rows)) for f in fields if rows and f in rows[0]}}


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
