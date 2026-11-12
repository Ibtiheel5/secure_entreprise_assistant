"""Exemples de pertinence synthétiques (requête, passage, label) à partir des faits du corpus.
 - positif       : chunk de la version ACTIVE contenant la réponse
 - hard negative : autres chunks du MÊME département
 - easy negative : chunks d'AUTRES départements
Le split est décidé par document (tous les exemples d'un document dans le même split) => pas de fuite train/test."""
import argparse
import random

from app.documents.chunking import chunk_text
from ml.datasets.common import assign_splits, check_no_leakage, read_jsonl, stats, write_jsonl


def make_examples(rows: list[dict], hard: int = 3, easy: int = 2, seed: int = 7,
                  chunk_size: int = 800, overlap: int = 120) -> list[dict]:
    rng = random.Random(seed)
    active = [r for r in rows if r["status"] == "ACTIVE"]
    chunks = [(r["doc_id"], r["department"], c) for r in active for c in chunk_text(r["text"], chunk_size, overlap)]
    splits = assign_splits(r["doc_id"] for r in active if r["facts"])
    out = []
    for r in active:
        for fi, fact in enumerate(r["facts"]):
            pos = [c for did, _, c in chunks if did == r["doc_id"] and fact["answer"] in c]
            if not pos:
                raise ValueError(f"{r['doc_id']}: answer {fact['answer']!r} not found in any chunk")
            qid, split = f"{r['doc_id']}#{fi}", splits[r["doc_id"]]
            base = {"query_id": qid, "query": fact["question"], "doc_id": r["doc_id"], "split": split, "source": "synthetic"}
            out.append({**base, "passage": pos[0], "label": 1.0, "kind": "positive"})
            same = [c for did, dep, c in chunks if dep == r["department"] and did != r["doc_id"]]
            other = [c for did, dep, c in chunks if dep != r["department"]]
            for c in rng.sample(same, min(hard, len(same))):
                out.append({**base, "passage": c, "label": 0.0, "kind": "hard_negative"})
            for c in rng.sample(other, min(easy, len(other))):
                out.append({**base, "passage": c, "label": 0.0, "kind": "easy_negative"})
    check_no_leakage(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/synthetic/docs.jsonl")
    ap.add_argument("--out", default="data/processed/synthetic_pairs.jsonl")
    ap.add_argument("--hard", type=int, default=3)
    ap.add_argument("--easy", type=int, default=2)
    a = ap.parse_args()
    ex = make_examples(list(read_jsonl(a.docs)), a.hard, a.easy)
    write_jsonl(a.out, ex)
    print(stats(ex))


if __name__ == "__main__":
    main()
