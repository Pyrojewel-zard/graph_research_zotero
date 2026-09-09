from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import httpx


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    model: str

    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingProvider:
    """Minimal `/embeddings` client for hosted or local compatible endpoints."""

    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 120.0

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise EmbeddingError("cannot embed empty research signature")

        url = f"{self.base_url.rstrip('/')}/embeddings"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = httpx.post(
                url,
                headers=headers,
                json={"model": self.model, "input": text},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"embedding request failed: {exc}") from exc

        payload = response.json()
        try:
            vector = payload["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingError("embedding endpoint returned an unexpected payload") from exc

        if not isinstance(vector, list) or not vector:
            raise EmbeddingError("embedding endpoint returned an empty vector")
        try:
            return [float(value) for value in vector]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("embedding vector contains non-numeric values") from exc


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("vectors must be non-empty and have the same dimension")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
