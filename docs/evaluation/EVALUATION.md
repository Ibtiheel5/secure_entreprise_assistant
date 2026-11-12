# Model evaluation

## Current status (honest)
- **The reranker fine-tuning has NOT been run.** The build environment had no access to Hugging Face (models/datasets) and no GPU.
  Consequently **no baseline-vs-fine-tuned numbers exist and no improvement is claimed.**
- Implemented and unit-tested: ranking metrics (MRR@10, NDCG@10, Recall@10, Precision@5), baseline/candidate comparison with a
  computed verdict, pair building, splits without leakage, pointwise evaluation with an injectable scorer.
- Implemented but **not executed**: `ml/training/train_reranker.py` (PyTorch/Transformers, CPU/GPU, BCE objective, per-epoch val loss,
  best-checkpoint saving, MLflow tracking/registry) and `ml/evaluation/evaluate_reranker.py` (model loading/scoring).

## How to produce real results
```bash
pip install -r backend/requirements.txt -r ml/requirements.txt
python -m ml.datasets.download msmarco --limit 20000 && python -m ml.preprocessing.msmarco --n-queries 20000
python -m ml.datasets.synthetic.generate && python -m ml.datasets.synthetic.make_relevance
export MLFLOW_TRACKING_URI=http://localhost:5000
python -m ml.training.train_reranker --train data/processed/msmarco_pairs.jsonl data/processed/synthetic_pairs.jsonl \
    --out ml/models/ft-1 --epochs 2 --max-train-samples 50000 --registered-name enterprise-reranker
python -m ml.evaluation.evaluate_reranker --test data/processed/msmarco_pairs.jsonl data/processed/synthetic_pairs.jsonl \
    --finetuned ml/models/ft-1 --mlflow --register-db
```
Then open the MLOps dashboard (baseline vs fine-tuned, deltas computed from stored metrics) and deploy the version if the verdict
is acceptable. Judge on the synthetic **and** MS MARCO test splits; the synthetic test split is small.

## Retrieval/RAG quality
Not measured here: the offline tests use a lexical hash embedder and a scripted LLM to verify *security and plumbing*, not answer
quality. Evaluate with `sentence-transformers` + Ollama on MultiDoc2Dial / the synthetic questions before drawing conclusions.
`MIN_RETRIEVAL_SCORE` (default 0.2) must be calibrated on that evaluation.
