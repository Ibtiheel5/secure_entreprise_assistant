from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    seed_password: str | None = None
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- embeddings ("hash" = déterministe, SANS sémantique : réservé aux tests / démo hors-ligne, jamais implicite)
    embedding_backend: str = "sentence-transformers"  # sentence-transformers | hash
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- reranker (none = garde l'ordre vectoriel, choix explicite)
    reranker_backend: str = "cross-encoder"  # cross-encoder | none
    reranker_base_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_path: str | None = None  # modèle fine-tuné local (prioritaire sur le modèle "déployé" en base)

    # --- LLM (Ollama)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout_s: int = 120

    # --- ingestion / RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 30
    min_retrieval_score: float = 0.2  # similarité cosinus minimale ; à calibrer sur le jeu d'évaluation
    rerank_top_n: int = 5
    max_question_chars: int = 2000
    upload_dir: str = "./uploads"
    max_upload_mb: int = 20
    security_report_path: str = "./reports/security_report.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
