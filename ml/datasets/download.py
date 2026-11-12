"""Téléchargement d'un échantillon brut -> data/raw/<dataset>/*.jsonl (nécessite l'accès réseau à Hugging Face).
  python -m ml.datasets.download msmarco --limit 20000
En cas d'échec réseau/dépôt introuvable : erreur explicite, JAMAIS de données de remplacement fabriquées."""
import argparse
import sys

from ml.datasets.common import write_jsonl
from ml.datasets.sources import SOURCES


def fetch(repo: str, config: str | None, split: str, limit: int):
    from datasets import load_dataset
    ds = load_dataset(repo, config, split=split, streaming=True)
    for i, row in enumerate(ds):
        if i >= limit:
            break
        yield dict(row)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=sorted(SOURCES))
    ap.add_argument("--repo", help="surcharge l'identifiant HF (obligatoire pour enterprise_rag_bench)")
    ap.add_argument("--config")
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--out-dir", default="data/raw")
    a = ap.parse_args(argv)
    src = SOURCES[a.dataset]
    repo = a.repo or src.get("hf_repo")
    if not repo:
        sys.exit(f"{a.dataset}: no repository configured. {src['license_note']}")
    jobs = ([(a.config or c, name) for name, c in src["hf_configs"].items()] if "hf_configs" in src
            else [(a.config or src.get("hf_config"), "data")])
    for config, name in jobs:
        try:
            n = write_jsonl(f"{a.out_dir}/{a.dataset}/{name}.{a.split}.jsonl", fetch(repo, config, a.split, a.limit))
        except Exception as exc:
            sys.exit(f"Download failed for {repo} ({config}): {type(exc).__name__}: {exc}\n"
                     f"Check network access / repository id. Official page: {src['official']}")
        print(f"{a.dataset}/{name}: {n} rows")


if __name__ == "__main__":
    main()
