"""CUAD -> docs.jsonl + eval.jsonl. Schéma attendu (HF theatticusproject/cuad-qa) : id, title, context, question, answers{text[], answer_start[]}.
Les contrats NE sont PAS classés RH : département POLICIES (légal), classification CONFIDENTIAL, accès configurable (défaut : CEO)."""
import argparse

from ml.datasets.common import read_jsonl, require_fields, write_jsonl


def convert(rows, allowed_roles=("CEO",)):
    docs, evals = {}, []
    for r in rows:
        require_fields(r, ["id", "title", "context", "question", "answers"], "cuad")
        did = f"cuad:{r['title']}"
        docs.setdefault(did, {"doc_id": did, "title": r["title"], "text": r["context"], "source": "cuad",
                              "department": "POLICIES", "classification": "CONFIDENTIAL",
                              "allowed_roles": list(allowed_roles), "version": 1, "status": "ACTIVE",
                              "metadata": {"domain": "legal_contract"}})
        texts = r["answers"].get("text") or []
        if texts:  # questions sans réponse exclues de l'évaluation de retrieval
            evals.append({"query_id": f"cuad:{r['id']}", "query": r["question"], "relevant_doc_ids": [did],
                          "answer": texts[0], "source": "cuad"})
    return list(docs.values()), evals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/cuad/data.train.jsonl")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--roles", default="CEO", help="rôles autorisés, séparés par des virgules")
    a = ap.parse_args()
    docs, ev = convert(read_jsonl(a.raw), a.roles.split(","))
    write_jsonl(f"{a.out_dir}/cuad_docs.jsonl", docs); write_jsonl(f"{a.out_dir}/cuad_eval.jsonl", ev)
    print({"contracts": len(docs), "eval_queries": len(ev)})


if __name__ == "__main__":
    main()
