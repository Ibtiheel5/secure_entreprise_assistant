from typing import Protocol

import httpx

from app.config import get_settings


class LLMUnavailable(Exception):
    pass


class LLM(Protocol):
    def generate(self, system: str, user: str) -> str: ...


class OllamaClient:
    def generate(self, system: str, user: str) -> str:
        s = get_settings()
        try:
            r = httpx.post(
                f"{s.ollama_url}/api/chat",
                json={"model": s.ollama_model, "stream": False, "options": {"temperature": 0.1},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                timeout=s.llm_timeout_s,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMUnavailable(f"LLM service unavailable ({type(exc).__name__})") from exc


_override: LLM | None = None


def set_llm(llm: LLM | None) -> None:
    global _override
    _override = llm


def get_llm() -> LLM:
    return _override or OllamaClient()
