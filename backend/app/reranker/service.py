"""Cross-encoder reranker. Modèle utilisé (priorité) : RERANKER_PATH > version marquée « déployée » (table
model_experiments) > modèle de base. L'ordre vectoriel est conservé seulement si RERANKER_BACKEND=none (choix explicite)."""
import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import ModelExperiment

log = logging.getLogger("reranker")


class Reranker(Protocol):
    name: str
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_path: str):
        from sentence_transformers import CrossEncoder  # import tardif
        self.name = model_path
        self.model = CrossEncoder(model_path)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return [float(x) for x in self.model.predict([(query, p) for p in passages])]


class NoopReranker:
    name = "none"

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(len(passages) - i) for i in range(len(passages))]  # conserve l'ordre d'entrée


_override: Reranker | None = None
_cache: dict[str, Reranker] = {}


def set_reranker(r: Reranker | None) -> None:
    global _override
    _override = r


def resolve_model_path(db: Session) -> str:
    s = get_settings()
    if s.reranker_path:
        return s.reranker_path
    deployed = db.scalar(select(ModelExperiment).where(ModelExperiment.is_deployed.is_(True)))
    if deployed and deployed.params and deployed.params.get("model_path"):
        return deployed.params["model_path"]
    return s.reranker_base_model


def get_reranker(db: Session) -> Reranker:
    if _override:
        return _override
    s = get_settings()
    if s.reranker_backend == "none":
        return NoopReranker()
    if s.reranker_backend != "cross-encoder":
        raise RuntimeError(f"Unknown RERANKER_BACKEND={s.reranker_backend!r}")
    path = resolve_model_path(db)
    if path not in _cache:
        log.info("loading reranker %s", path)
        _cache[path] = CrossEncoderReranker(path)
    return _cache[path]
