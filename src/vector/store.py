from __future__ import annotations

import asyncio
import math
from typing import Any

from src.domain.exceptions import VectorStoreException
from src.domain.interfaces import VectorStore
from src.domain.vector import (
    DistanceMetric,
    FilterOperator,
    MetadataFilter,
    VectorRecord,
    VectorSearchResult,
)


def _dot_product(vec_a: list[float], vec_b: list[float]) -> float:
    return sum(a * b for a, b in zip(vec_a, vec_b))


def _magnitude(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    mag_a = _magnitude(vec_a)
    mag_b = _magnitude(vec_b)
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return _dot_product(vec_a, vec_b) / (mag_a * mag_b)


def _euclidean_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dist_sq = sum((a - b) ** 2 for a, b in zip(vec_a, vec_b))
    dist = math.sqrt(dist_sq)
    # Convert L2 distance into a normalized similarity score in (0, 1]
    return 1.0 / (1.0 + dist)


def _evaluate_filter_operator(payload_val: Any, op: FilterOperator, filter_val: Any) -> bool:
    if op == FilterOperator.EQ:
        return payload_val == filter_val
    if op == FilterOperator.NE:
        return payload_val != filter_val
    if op == FilterOperator.GT:
        return payload_val is not None and payload_val > filter_val
    if op == FilterOperator.GTE:
        return payload_val is not None and payload_val >= filter_val
    if op == FilterOperator.LT:
        return payload_val is not None and payload_val < filter_val
    if op == FilterOperator.LTE:
        return payload_val is not None and payload_val <= filter_val
    if op == FilterOperator.IN:
        return isinstance(filter_val, (list, tuple, set)) and payload_val in filter_val
    if op == FilterOperator.NIN:
        return isinstance(filter_val, (list, tuple, set)) and payload_val not in filter_val
    if op == FilterOperator.CONTAINS:
        if isinstance(payload_val, (list, tuple, set)):
            return filter_val in payload_val
        if isinstance(payload_val, str):
            return str(filter_val) in payload_val
        return False
    return False


def _evaluate_filters(payload: dict[str, Any], filters: list[MetadataFilter]) -> bool:
    for f in filters:
        payload_val = payload.get(f.field)
        if not _evaluate_filter_operator(payload_val, f.operator, f.value):
            return False
    return True


class InMemoryVectorStore(VectorStore):
    """In-memory vector store with thread safety, metadata filtering, and flexible metrics."""

    def __init__(self, default_metric: DistanceMetric = DistanceMetric.COSINE):
        self._records: dict[str, VectorRecord] = {}
        self._lock = asyncio.Lock()
        self.default_metric = default_metric

    async def upsert(self, records: list[VectorRecord]) -> int:
        if not records:
            return 0
        async with self._lock:
            for record in records:
                if not record.vector:
                    raise VectorStoreException(f"Record '{record.id}' has empty vector")
                self._records[record.id] = record
            return len(records)

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: list[MetadataFilter] | None = None,
        min_score: float | None = None,
        distance_metric: DistanceMetric | None = None,
    ) -> list[VectorSearchResult]:
        if not query_vector:
            raise VectorStoreException("Query vector cannot be empty")
        if top_k <= 0:
            return []

        metric = distance_metric or self.default_metric
        filters = filters or []

        results: list[VectorSearchResult] = []

        async with self._lock:
            for record in self._records.values():
                if len(record.vector) != len(query_vector):
                    raise VectorStoreException(
                        f"Dimension mismatch: query dimension ({len(query_vector)}) != "
                        f"record dimension ({len(record.vector)})"
                    )

                if filters and not _evaluate_filters(record.payload, filters):
                    continue

                if metric == DistanceMetric.COSINE:
                    score = _cosine_similarity(query_vector, record.vector)
                elif metric == DistanceMetric.DOT_PRODUCT:
                    score = _dot_product(query_vector, record.vector)
                elif metric == DistanceMetric.EUCLIDEAN:
                    score = _euclidean_similarity(query_vector, record.vector)
                else:
                    raise VectorStoreException(f"Unsupported distance metric: {metric}")

                if min_score is not None and score < min_score:
                    continue

                results.append(
                    VectorSearchResult(
                        id=record.id,
                        score=score,
                        payload=record.payload,
                        vector=record.vector,
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        deleted_count = 0
        async with self._lock:
            for record_id in ids:
                if record_id in self._records:
                    del self._records[record_id]
                    deleted_count += 1
        return deleted_count

    async def count(self) -> int:
        async with self._lock:
            return len(self._records)
