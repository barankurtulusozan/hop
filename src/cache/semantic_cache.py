from __future__ import annotations

import logging
import math
import time
import uuid
from typing import Any

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.domain.cache import CacheEntry, CacheResult, CacheStatus, SemanticCacheConfig
from src.domain.interfaces import EmbeddingProvider

logger = logging.getLogger("llm_orchestrator.cache")


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    """Vector similarity semantic cache for sub-millisecond zero-cost prompt response bypass."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        config: SemanticCacheConfig | None = None,
    ):
        self.embedding_provider = embedding_provider or MockEmbeddingAdapter()
        self.config = config or SemanticCacheConfig()
        self._entries: list[CacheEntry] = []

    async def _embed_prompt(self, text: str) -> list[float]:
        from src.domain.vector import EmbeddingRequest
        resp = await self.embedding_provider.embed(EmbeddingRequest(input_texts=[text]))
        return resp.embeddings[0]

    async def get(self, prompt: str) -> CacheResult:
        if not self._entries:
            return CacheResult(status=CacheStatus.MISS)

        prompt_emb = await self._embed_prompt(prompt)
        best_entry: CacheEntry | None = None
        best_sim = -1.0

        for entry in self._entries:
            sim = cosine_similarity(prompt_emb, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry and best_sim >= self.config.similarity_threshold:
            logger.info(f"Semantic Cache HIT (similarity={best_sim:.4f} >= {self.config.similarity_threshold})")
            return CacheResult(status=CacheStatus.HIT, entry=best_entry, similarity_score=best_sim)

        logger.info(f"Semantic Cache MISS (best_sim={best_sim:.4f} < {self.config.similarity_threshold})")
        return CacheResult(status=CacheStatus.MISS, similarity_score=best_sim if best_sim > 0 else 0.0)

    async def set(self, prompt: str, response: Any) -> CacheEntry:
        prompt_emb = await self._embed_prompt(prompt)
        entry = CacheEntry(
            key=f"cache_{uuid.uuid4().hex[:10]}",
            prompt=prompt,
            embedding=prompt_emb,
            response=response,
            created_at=time.time(),
        )
        self._entries.append(entry)
        logger.info(f"Stored response in Semantic Cache for prompt '{prompt[:30]}...'")
        return entry

    async def clear(self) -> None:
        self._entries.clear()
