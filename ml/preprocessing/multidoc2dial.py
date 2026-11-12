"""MultiDoc2Dial -> docs.jsonl + eval.jsonl. Schémas attendus (HF IBM/multidoc2dial) :
 document_domain : doc_id, title, domain, doc_text ; dialogue_domain : dial_id, domain, turns[{role, utterance, references[{doc_id}]}].
Toute divergence de schéma lève une erreur explicite."""
import argparse

from ml.datasets.common import read_jsonl, require_fields, stats, write_jsonl


def convert_documents(rows, roles=("CEO", "HR_MANAGER", "HR_EMPLOYEE", "IT_MANAGER", "IT_EMPLOYEE", "FINANCE_MANAGER",
                                   "FINANCE_EMPLOYEE", "GENERAL_EMPLOYEE")):
    for r in rows:
        require_fields(r, ["doc_id", "title", "domain", "doc_text"], "multidoc2dial.documents")
        yield {"doc_id": f"md2d:{r['doc_id']}", "title": r["title"], "text": r["doc_text"], "source": "multidoc2dial",
               "department": "POLICIES", "classification": "PUBLIC", "allowed_roles": list(roles), "version": 1,
               "status": "ACTIVE", "metadata": {"domain": r["domain"]}}


def convert_dialogues(rows):
    for dial in rows:
        require_fields(dial, ["dial_id", "turns"], "multidoc2dial.dialogues")
        last_user = None
        for i, turn in enumerate(dial["turns"]):
            require_fields(turn, ["role", "utterance"], "multidoc2dial.turns")
            if turn["role"] == "user":
                last_user = turn["utterance"]
            elif turn["role"] == "agent" and last_user:
                ids = sorted({f"md2d:{ref['doc_id']}" for ref in (turn.get("references") or []) if "doc_id" in ref})
                if ids:
                    yield {"query_id": f"{dial['dial_id']}#{i}", "query": last_user, "relevant_doc_ids": ids,
                           "answer": turn["utterance"], "source": "multidoc2dial"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-raw", default="data/raw/multidoc2dial/documents.train.jsonl")
    ap.add_argument("--dialogues-raw", default="data/raw/multidoc2dial/dialogues.train.jsonl")
    ap.add_argument("--out-dir", default="data/processed")
    a = ap.parse_args()
    nd = write_jsonl(f"{a.out_dir}/multidoc2dial_docs.jsonl", convert_documents(read_jsonl(a.docs_raw)))
    ev = list(convert_dialogues(read_jsonl(a.dialogues_raw)))
    write_jsonl(f"{a.out_dir}/multidoc2dial_eval.jsonl", ev)
    print({"documents": nd, "eval_queries": len(ev)})


if __name__ == "__main__":
    main()
