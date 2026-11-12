"""Inspection d'un JSONL brut avant d'écrire/ajuster le prétraitement : champs, types, exemple, valeurs manquantes."""
import argparse
import itertools
import json
from collections import Counter

from ml.datasets.common import read_jsonl


def inspect(path: str, n: int = 1000) -> dict:
    rows = list(itertools.islice(read_jsonl(path), n))
    types, missing = {}, Counter()
    for r in rows:
        for k, v in r.items():
            types.setdefault(k, Counter())[type(v).__name__] += 1
            if v in (None, "", [], {}):
                missing[k] += 1
    return {"rows_sampled": len(rows), "fields": {k: dict(v) for k, v in types.items()}, "empty_values": dict(missing),
            "example": rows[0] if rows else None}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("-n", type=int, default=1000)
    a = ap.parse_args()
    print(json.dumps(inspect(a.path, a.n), indent=2, ensure_ascii=False, default=str)[:6000])
