from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

import httpx

from app.core.config import Settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    @property
    def reference(self) -> str: ...

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]: ...


def local_hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    for word in re.findall(r"\w+", text.lower()):
        digest = hashlib.sha256(word.encode()).digest()
        vector[int.from_bytes(digest[:2], "big") % dimensions] += 1 if digest[2] % 2 else -1
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


class LocalHashEmbeddingProvider:
    def __init__(self, dimensions: int) -> None:
        self._dimensions = dimensions

    @property
    def reference(self) -> str:
        return f"local-hash-v2-{self._dimensions}"

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [local_hash_embedding(text, self._dimensions) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self._base_url = str(settings.ai_provider_base_url).rstrip("/")
        self._api_key = settings.ai_provider_api_key or ""
        self._model = settings.knowledge_embedding_model
        self._dimensions = settings.knowledge_embedding_dimensions
        self._batch_size = settings.knowledge_embedding_batch_size
        self._timeout = settings.ai_provider_timeout_seconds

    @property
    def reference(self) -> str:
        return f"openai-compatible:{self._model}:{self._dimensions}"[:100]

    async def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        if not self._api_key:
            raise EmbeddingError("O provedor de embeddings não possui uma chave configurada.")
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) as client:
            for start in range(0, len(texts), self._batch_size):
                batch = list(texts[start : start + self._batch_size])
                try:
                    response = await client.post(
                        f"{self._base_url}/embeddings",
                        json={
                            "model": self._model,
                            "input": batch,
                            "dimensions": self._dimensions,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise EmbeddingError(
                        "O provedor de embeddings está temporariamente indisponível."
                    ) from exc
                data = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(data, list) or len(data) != len(batch):
                    raise EmbeddingError("O provedor devolveu uma quantidade inválida de vetores.")
                if not all(isinstance(item, dict) for item in data):
                    raise EmbeddingError("O provedor devolveu vetores em formato inválido.")
                ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
                for item in ordered:
                    vector = item.get("embedding") if isinstance(item, dict) else None
                    if not isinstance(vector, list) or len(vector) != self._dimensions:
                        raise EmbeddingError("O provedor devolveu um vetor com dimensão inválida.")
                    numeric = [float(value) for value in vector]
                    if not all(math.isfinite(value) for value in numeric):
                        raise EmbeddingError("O provedor devolveu um vetor inválido.")
                    vectors.append(numeric)
        return vectors


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.knowledge_embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(settings)
    return LocalHashEmbeddingProvider(settings.knowledge_embedding_dimensions)
