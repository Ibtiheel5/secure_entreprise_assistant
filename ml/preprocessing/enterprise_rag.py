"""EnterpriseRAG-Bench : le schéma réel n'est PAS supposé. Après vérification du dépôt et inspection (inspect_dataset.py),
fournir le mapping des champs :  --map '{"doc_id":"...","title":"...","text":"..."}' (documents) et/ou
--qmap '{"query_id":"...","query":"...","relevant":"..."}' (questions). Les identifiants d'origine sont conservés."""
import argparse
import json

from ml.datasets.common import read_jsonl, require_fields, write_jsonl


def convert_docs(rows, m: dict, roles, department="POLICIES", classification="INTERNAL"):
    for r in rows:
        require_fields(r, [m["doc_id"], m["text"]], "enterprise_rag.docs")
        yield {"doc_id": f"erb:{r[m['doc_id']]}", "title": str(r.get(m.get("title", ""), r[m["doc_id"]])), "text": r[m["text"]],
               "source": "enterprise_rag_bench", "department": department, "classification": classification,
               "allowed_roles": roles, "version": 1, "status": "ACTIVE", "metadata": {"original_id": r[m["doc_id"]]}}


def convert_eval(rows, m: dict):
    for r in rows:
        require_fields(r, [m["query_id"], m["query"], m["relevant"]], "enterprise_rag.eval")
        rel = r[m["relevant"]]
        rel = rel if isinstance(rel, list) else [rel]
        yield {"query_id": f"erb:{r[m['query_id']]}", "query": r[m["query"]],
               "relevant_doc_ids": [f"erb:{x}" for x in rel], "source": "enterprise_rag_bench"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-raw"); ap.add_argument("--eval-raw")
    ap.add_argument("--map", type=json.loads); ap.add_argument("--qmap", type=json.loads)
    ap.add_argument("--roles", default="GENERAL_EMPLOYEE,CEO")
    ap.add_argument("--out-dir", default="data/processed")
    a = ap.parse_args()
    if a.docs_raw:
        print("docs:", write_jsonl(f"{a.out_dir}/erb_docs.jsonl", convert_docs(read_jsonl(a.docs_raw), a.map, a.roles.split(","))))
    if a.eval_raw:
        print("eval:", write_jsonl(f"{a.out_dir}/erb_eval.jsonl", convert_eval(read_jsonl(a.eval_raw), a.qmap)))


if __name__ == "__main__":
    main()
