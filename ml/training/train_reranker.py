"""Fine-tuning du cross-encoder (PyTorch/Transformers). Objectif : BCE pointwise sur paires (requête, passage) positives/
négatives (hard + easy), objectif standard des cross-encoders MS MARCO ; la qualité est jugée par les métriques de RANKING
(MRR@10, NDCG@10...) sur un test séparé (ml/evaluation/evaluate_reranker.py).
  python -m ml.training.train_reranker --train data/processed/msmarco_pairs.jsonl data/processed/synthetic_pairs.jsonl \
      --out ml/models/ft-1 --epochs 2 --max-train-samples 50000
CPU ou GPU (auto). Rien n'est affirmé sur l'amélioration avant l'évaluation."""
import argparse
import random
import time

from ml.datasets.common import file_sha256, read_jsonl


def load_pairs(paths, splits, max_samples=None, seed=13):
    rows = [r for p in paths for r in read_jsonl(p) if r.get("split") in splits]
    random.Random(seed).shuffle(rows)
    return rows[:max_samples] if max_samples else rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--base-model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--max-train-samples", type=int)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--experiment", default="reranker-finetuning")
    ap.add_argument("--run-name")
    ap.add_argument("--registered-name", default=None)
    a = ap.parse_args(argv)

    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    from ml.mlops.mlflow_utils import log_metrics, log_model_dir, tracked_run

    torch.manual_seed(a.seed)
    device = "cuda" if a.device == "auto" and torch.cuda.is_available() else ("cpu" if a.device == "auto" else a.device)
    train = load_pairs(a.train, {"train"}, a.max_train_samples, a.seed)
    val = load_pairs(a.train, {"val"}, None, a.seed)
    if not train or not val:
        raise SystemExit("Need non-empty train and val splits in the pair files")
    tok = AutoTokenizer.from_pretrained(a.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(a.base_model, num_labels=1).to(device)

    def collate(batch):
        enc = tok([b["query"] for b in batch], [b["passage"] for b in batch], truncation=True, max_length=a.max_len,
                  padding=True, return_tensors="pt")
        return enc, torch.tensor([b["label"] for b in batch], dtype=torch.float)

    tl = DataLoader(train, batch_size=a.batch_size, shuffle=True, collate_fn=collate)
    vl = DataLoader(val, batch_size=a.batch_size, collate_fn=collate)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    total = len(tl) * a.epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * total), total)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    def run_val():
        model.eval(); tot = n = 0
        with torch.no_grad():
            for enc, y in vl:
                logits = model(**{k: v.to(device) for k, v in enc.items()}).logits.squeeze(-1)
                tot += loss_fn(logits, y.to(device)).item() * len(y); n += len(y)
        return tot / n

    params = {"base_model": a.base_model, "epochs": a.epochs, "batch_size": a.batch_size, "lr": a.lr, "max_len": a.max_len,
              "train_rows": len(train), "val_rows": len(val), "device": device, "seed": a.seed,
              "dataset_sha256": ",".join(file_sha256(p)[:12] for p in a.train), "objective": "bce_pointwise"}
    with tracked_run(a.experiment, a.run_name or a.out.rstrip("/").split("/")[-1], params) as run:
        best, t0 = float("inf"), time.time()
        for epoch in range(1, a.epochs + 1):
            model.train(); running = 0.0
            for i, (enc, y) in enumerate(tl, 1):
                loss = loss_fn(model(**{k: v.to(device) for k, v in enc.items()}).logits.squeeze(-1), y.to(device))
                loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(); running += loss.item()
            v = run_val()
            log_metrics({"train_loss": running / len(tl), "val_loss": v}, step=epoch)
            print(f"epoch {epoch}: train_loss={running / len(tl):.4f} val_loss={v:.4f}")
            if v < best:
                best = v; model.save_pretrained(a.out); tok.save_pretrained(a.out)  # checkpoint = meilleur val_loss
        log_metrics({"best_val_loss": best, "train_duration_s": time.time() - t0})
        version = log_model_dir(a.out, a.registered_name)
        print(f"best val_loss={best:.4f} -> {a.out}  mlflow_run={run.info.run_id}  registry_version={version}")


if __name__ == "__main__":
    main()
