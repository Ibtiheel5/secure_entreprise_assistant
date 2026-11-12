"""Registre des sources. Les identifiants HF et les licences ci-dessous sont des POINTS DE DÉPART à VÉRIFIER sur les pages
officielles avant tout usage (docs/datasets/DATASETS.md) ; rien n'a été téléchargé ni confirmé automatiquement."""
SOURCES = {
    "msmarco": {"official": "https://microsoft.github.io/msmarco/", "hf_repo": "microsoft/ms_marco", "hf_config": "v2.1",
                "license_note": "Vérifier : conditions d'usage MS MARCO (usage non commercial/recherche à confirmer).", "purpose": "reranker"},
    "multidoc2dial": {"official": "https://github.com/IBM/multidoc2dial", "hf_repo": "IBM/multidoc2dial",
                      "hf_configs": {"documents": "document_domain", "dialogues": "dialogue_domain"},
                      "license_note": "Vérifier la licence dans le dépôt IBM.", "purpose": "grounded RAG eval"},
    "cuad": {"official": "https://www.atticusprojectai.org/cuad", "hf_repo": "theatticusproject/cuad-qa",
             "license_note": "Vérifier la licence sur la page officielle (CC BY 4.0 annoncée, à confirmer).", "purpose": "legal docs"},
    "enterprise_rag_bench": {"official": None, "hf_repo": None,
                             "license_note": "Dépôt NON vérifié : lancer ml/datasets/verify_enterprise_rag_bench.py puis fournir --repo.",
                             "purpose": "enterprise retrieval eval"},
}
