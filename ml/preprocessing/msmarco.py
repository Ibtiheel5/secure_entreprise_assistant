"""MS MARCO -> paires (requête, passage, label) pour le cross-encoder. Échantillonnage configurable, dédoublonné,
split par requête. Schéma attendu (HF microsoft/ms_marco v2.1) : query_id, query, passages{is_selected[], passage_text[]}."""
import argparse
import random

from ml.datasets.common import (check_no_leakage, dedupe, read_jsonl, require_fields, split_of, stats, write_jsonl)


def build_pairs(rows, n_queries: int = 20000, hard: int = 3, easy: int = 2, seed: int = 13, max_passage_chars: int = 2000):
    rng = random.Random(seed)
    usable = []
    for r in rows:
        require_fields(r, ["query_id", "query", "passages"], "msmarco")
        require_fields(r["passages"], ["is_selected", "passage_text"], "msmarco.passages")
        sel, txt = r["passages"]["is_selected"], r["passages"]["passage_text"]
        if len(sel) != len(txt):
            continue  # ligne incohérente : ignorée (validation)
        pos = [t for s, t in zip(sel, txt) if s == 1 and t.strip()]
        neg = [t for s, t in zip(sel, txt) if s == 0 and t.strip()]
        if r["query"].strip() and pos:
            usable.append((str(r["query_id"]), r["query"].strip(), pos, neg))
    rng.shuffle(usable)
    usable = usable[:n_queries]
    pool = [t for _, _, _, neg in usable for t in neg] or [t for _, _, pos, _ in usable for t in pos]
    out = []
    for qid, q, pos, neg in usable:
        split = split_of(qid)
        base = {"query_id": qid, "query": q, "split": split, "source": "msmarco"}
        for p in pos:
            out.append({**base, "passage": p[:max_passage_chars], "label": 1.0, "kind": "positive"})
        for p in neg[:hard]:
            out.append({**base, "passage": p[:max_passage_chars], "label": 0.0, "kind": "hard_negative"})
        for p in rng.sample(pool, min(easy, len(pool))):
            if p not in pos and p not in neg:
                out.append({**base, "passage": p[:max_passage_chars], "label": 0.0, "kind": "easy_negative"})
    out = list(dedupe(out, ("query_id", "passage")))
    check_no_leakage(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/msmarco/data.train.jsonl")
    ap.add_argument("--out", default="data/processed/msmarco_pairs.jsonl")
    ap.add_argument("--n-queries", type=int, default=20000)
    ap.add_argument("--hard", type=int, default=3)
    ap.add_argument("--easy", type=int, default=2)
    a = ap.parse_args()
    pairs = build_pairs(read_jsonl(a.raw), a.n_queries, a.hard, a.easy)
    write_jsonl(a.out, pairs)
    print(stats(pairs))


if __name__ == "__main__":
    main()
