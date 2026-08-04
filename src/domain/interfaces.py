"""
Core port definition. This is the ONLY contract the orchestrator and business
code are allowed to depend on. No vendor SDK imports permitted here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterable

from src.domain.models import CompletionRequest, CompletionResponse, StreamChunk
from src.domain.vector import (
    DistanceMetric,
    EmbeddingRequest,
    EmbeddingResponse,
    MetadataFilter,
    VectorRecord,
    VectorSearchResult,
)


class LLMProvider(ABC):
    """Hexagonal port: every vendor adapter (OpenAI, Anthropic, Mock, ...) implements this."""

    #: Short, stable identifier used in telemetry and routing config, e.g. "openai", "anthropic".
    name: str

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a single, non-streaming completion.

        Implementations MUST raise only subclasses of
        `src.domain.exceptions.LLMException` -- vendor exceptions must be
        caught and translated before crossing this boundary.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        """Execute a streaming completion, yielding chunks as they arrive.

        Same exception-translation contract as `complete`.
        """
        raise NotImplementedError


class EmbeddingProvider(ABC):
    """Hexagonal port for dense vector embedding generation providers."""

    name: str

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality produced by this embedding provider/model."""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate vector embeddings for input texts.

        Implementations MUST raise only `EmbeddingException` or `RateLimitExceeded`.
        """
        raise NotImplementedError


class VectorStore(ABC):
    """Hexagonal port for vector database indexing and semantic retrieval engines."""

    @abstractmethod
    async def upsert(self, records: list[VectorRecord]) -> int:
        """Insert or update vector records in the index. Returns count of upserted records."""
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: list[MetadataFilter] | None = None,
        min_score: float | None = None,
        distance_metric: DistanceMetric | None = None,
    ) -> list[VectorSearchResult]:
        """Perform top-k similarity search given a query vector and optional metadata filters."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, ids: list[str]) -> int:
        """Delete records by ID. Returns count of deleted records."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of records currently indexed."""
        raise NotImplementedError

