import hashlib
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Feature hashing de mots : AUCUNE compréhension sémantique. Uniquement pour tests/démo hors-ligne
    (EMBEDDING_BACKEND=hash, choix explicite). Utile car il rend la similarité lexicale déterministe."""

    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for w in re.findall(r"\w+", t.lower()):
                h = int.from_bytes(hashlib.md5(w.encode()).digest()[:4], "little")
                v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
            n = np.linalg.norm(v)
            out.append((v / n if n else v).tolist())
        return out


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # import tardif (dépendance lourde)
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


_override: Embedder | None = None


def set_embedder(e: Embedder | None) -> None:
    global _override
    _override = e


@lru_cache
def _build() -> Embedder:
    s = get_settings()
    if s.embedding_backend == "hash":
        return HashEmbedder(s.embedding_dim)
    if s.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbedder(s.embedding_model)
    raise RuntimeError(f"Unknown EMBEDDING_BACKEND={s.embedding_backend!r}")


def get_embedder() -> Embedder:
    return _override or _build()
