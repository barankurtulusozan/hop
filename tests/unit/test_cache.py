import pytest

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.cache.semantic_cache import SemanticCache
from src.domain.cache import CacheStatus, SemanticCacheConfig


@pytest.mark.asyncio
async def test_semantic_cache_hit_and_miss():
    cache = SemanticCache(
        embedding_provider=MockEmbeddingAdapter(dimension=16),
        config=SemanticCacheConfig(similarity_threshold=0.90),
    )

    # Cache is empty initially
    res1 = await cache.get("What is hexagonal architecture?")
    assert res1.status == CacheStatus.MISS

    # Set cache entry
    await cache.set("What is hexagonal architecture?", "Hexagonal architecture decouples domain logic.")

    # Retrieve identical prompt -> HIT
    res2 = await cache.get("What is hexagonal architecture?")
    assert res2.status == CacheStatus.HIT
    assert res2.entry is not None
    assert res2.entry.response == "Hexagonal architecture decouples domain logic."
    assert res2.similarity_score >= 0.90
