from __future__ import annotations

import hashlib
import math
from typing import Sequence

from src.domain.interfaces import EmbeddingProvider
from src.domain.models import TokenUsage
from src.domain.vector import EmbeddingRequest, EmbeddingResponse


class MockEmbeddingAdapter(EmbeddingProvider):
    """Deterministic, zero-network mock embedding adapter for testing and offline development."""

    name = "mock"

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> list[float]:
        # Hash text to generate deterministic pseudo-random float components
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        for i in range(self._dimension):
            byte_val = seed_bytes[i % len(seed_bytes)]
            val = ((byte_val ^ (i & 0xFF)) / 255.0) - 0.5
            vector.append(val)

        # Normalize vector to unit length
        sq_sum = sum(x * x for x in vector)
        magnitude = math.sqrt(sq_sum) if sq_sum > 0 else 1.0
        return [x / magnitude for x in vector]

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        embeddings = [self._generate_vector(text) for text in request.input_texts]
        # Approximate token count: ~1 token per 4 characters
        total_tokens = sum(max(1, len(t) // 4) for t in request.input_texts)
        return EmbeddingResponse(
            embeddings=embeddings,
            model=request.model,
            token_usage=TokenUsage(prompt_tokens=total_tokens, completion_tokens=0),
        )
