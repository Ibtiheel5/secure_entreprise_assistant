# Datasets

**Status: no external dataset was downloaded or verified in the build environment** (no access to Hugging Face). The scripts below
implement download, inspection, validation, preprocessing, deduplication, leakage-free splitting and statistics. Repository ids and
licenses in `ml/datasets/sources.py` are starting points that **must be verified on the official pages**; nothing is fabricated or substituted.

| Dataset | Official source | Role | Script | Notes |
|---|---|---|---|---|
| EnterpriseRAG-Bench | not verified | enterprise retrieval eval | `verify_enterprise_rag_bench.py`, `preprocessing/enterprise_rag.py` | Repository **not confirmed**: run the verify script, then pass `--repo` and an explicit field mapping. Original ids are preserved. |
| MultiDoc2Dial | github.com/IBM/multidoc2dial | grounded conversational RAG eval | `preprocessing/multidoc2dial.py` | Schema (`document_domain`, `dialogue_domain`) written from documentation, **unvalidated on real files**; mismatches raise explicit errors. |
| MS MARCO | microsoft.github.io/msmarco | reranker fine-tuning | `preprocessing/msmarco.py` | Configurable query sampling, hard/easy negatives, dedupe, split by query. Check the usage terms before any non-research use. |
| CUAD | atticusprojectai.org/cuad | legal contracts | `preprocessing/cuad.py` | Contracts go to department `POLICIES`, classification `CONFIDENTIAL`, default role `CEO` — **never HR by default**. Verify the license. |
| Synthetic enterprise corpus | generated | full pipeline, tests, relevance data | `ml/datasets/synthetic/generate.py` | Fictional company "Nordia Systems"; 16 documents, 20 versions, 4 departments; every fact appears verbatim in its text. |

## Unified format
`docs.jsonl` `{doc_id, title, text, source, department, classification, allowed_roles, version, status, ...}` ·
`eval.jsonl` `{query_id, query, relevant_doc_ids, answer, source}` · `pairs.jsonl` `{query_id, query, passage, label, kind, split, source}`.

## Reproducible workflow
```bash
export PYTHONPATH=$PWD:$PWD/backend
python -m ml.datasets.synthetic.generate && python -m ml.datasets.synthetic.make_relevance
python -m ml.datasets.download msmarco --limit 20000 && python -m ml.datasets.inspect_dataset data/raw/msmarco/data.train.jsonl
python -m ml.preprocessing.msmarco --n-queries 20000
python scripts/ingest_corpus.py --docs data/synthetic/docs.jsonl --relevance data/processed/synthetic_pairs.jsonl
```
Synthetic relevance set (generated and verified here): 28 queries → 159 pairs (28 positive, 75 hard negative, 56 easy negative),
split by document into train/val/test with no overlap. It is small; it complements MS MARCO and cannot alone support strong conclusions.
