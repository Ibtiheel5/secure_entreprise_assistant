"""Cherche EnterpriseRAG-Bench sur le Hub Hugging Face. N'invente rien : si rien n'est trouvé, code de sortie 2."""
import sys


def main() -> int:
    try:
        from huggingface_hub import HfApi
        found = list(HfApi().list_datasets(search="EnterpriseRAG", limit=20)) + \
                list(HfApi().list_datasets(search="enterprise-rag", limit=20))
    except Exception as exc:
        print(f"Cannot query the Hugging Face Hub ({type(exc).__name__}: {exc}). Check network access.")
        return 2
    seen = {d.id: d for d in found}
    if not seen:
        print("No dataset matching 'EnterpriseRAG' found. Provide the official repository id manually "
              "(python -m ml.datasets.download enterprise_rag_bench --repo <org/name>) after verifying it.")
        return 2
    for d in seen.values():
        print(f"{d.id}  license={getattr(d, 'card_data', None) and d.card_data.get('license')}  downloads={d.downloads}")
    print("Verify the OFFICIAL repository and its license manually before using it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
