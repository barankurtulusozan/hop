from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from src.domain.exceptions import VectorStoreException
from src.domain.interfaces import VectorStore
from src.domain.vector import (
    DistanceMetric,
    MetadataFilter,
    VectorRecord,
    VectorSearchResult,
)


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric terms."""
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


@dataclass
class BM25Document:
    id: str
    content: str
    tokens: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


class BM25Retriever:
    """Okapi BM25 Lexical Retriever for sparse keyword matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: dict[str, BM25Document] = {}
        self.doc_freqs: dict[str, int] = {}
        self.doc_lengths: dict[str, int] = {}
        self.avg_doc_length: float = 0.0
        self.corpus_size: int = 0

    def add_documents(self, docs: list[BM25Document]) -> None:
        """Add or update documents in the BM25 index."""
        for doc in docs:
            tokens = tokenize(doc.content)
            doc.tokens = tokens
            
            # If replacing an existing doc, decrement old freqs
            if doc.id in self.documents:
                old_tokens = self.documents[doc.id].tokens
                for term in set(old_tokens):
                    self.doc_freqs[term] = max(0, self.doc_freqs.get(term, 1) - 1)

            self.documents[doc.id] = doc
            self.doc_lengths[doc.id] = len(tokens)

            # Update document frequencies
            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.corpus_size = len(self.documents)
        if self.corpus_size > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.corpus_size
        else:
            self.avg_doc_length = 0.0

    def remove_documents(self, doc_ids: list[str]) -> None:
        """Remove documents from index."""
        for doc_id in doc_ids:
            if doc_id in self.documents:
                tokens = self.documents[doc_id].tokens
                for term in set(tokens):
                    self.doc_freqs[term] = max(0, self.doc_freqs.get(term, 1) - 1)
                del self.documents[doc_id]
                del self.doc_lengths[doc_id]

        self.corpus_size = len(self.documents)
        if self.corpus_size > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.corpus_size
        else:
            self.avg_doc_length = 0.0

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Search index with raw text query and return (doc_id, bm25_score) list."""
        query_tokens = tokenize(query)
        if not query_tokens or self.corpus_size == 0:
            return []

        scores: dict[str, float] = {}

        for token in query_tokens:
            doc_freq = self.doc_freqs.get(token, 0)
            if doc_freq == 0:
                continue

            # Okapi BM25 IDF formula with smoothing
            idf = math.log((self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)

            for doc_id, doc in self.documents.items():
                term_freq = doc.tokens.count(token)
                if term_freq == 0:
                    continue

                doc_len = self.doc_lengths[doc_id]
                denom = term_freq + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_length or 1.0)))
                score = idf * (term_freq * (self.k1 + 1.0)) / denom
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        sorted_results = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return sorted_results[:top_k]


class ReciprocalRankFusion:
    """Merges multiple ranked lists of document IDs using Reciprocal Rank Fusion (RRF)."""

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    def merge(
        self,
        ranked_lists: list[list[tuple[str, float]]],
        weights: list[float] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Merge multiple (doc_id, score) lists.
        Formula: RRF_score(d) = sum_m( weight_m / (k + rank_m(d)) )
        """
        if not ranked_lists:
            return []

        if weights is None:
            weights = [1.0] * len(ranked_lists)

        combined_scores: dict[str, float] = {}

        for list_idx, rank_list in enumerate(ranked_lists):
            w = weights[list_idx]
            for rank, (doc_id, _) in enumerate(rank_list, start=1):
                rrf_score = w / (self.rrf_k + rank)
                combined_scores[doc_id] = combined_scores.get(doc_id, 0.0) + rrf_score

        sorted_combined = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_combined


class HybridVectorStore:
    """Hybrid Search Engine combining dense vector search and sparse BM25 retrieval."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_retriever: BM25Retriever | None = None,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.rrf = ReciprocalRankFusion(rrf_k=rrf_k)

    async def upsert(self, records: list[VectorRecord]) -> int:
        """Upsert records into both dense vector store and sparse BM25 index."""
        if not records:
            return 0

        # Upsert into dense vector store
        upserted_count = await self.vector_store.upsert(records)

        # Index in BM25
        bm25_docs: list[BM25Document] = []
        for record in records:
            # Extract textual content from payload
            content = record.payload.get("content") or record.payload.get("text") or record.payload.get("title") or ""
            if not isinstance(content, str):
                content = str(content)
            bm25_docs.append(
                BM25Document(
                    id=record.id,
                    content=content,
                    payload=record.payload,
                )
            )

        self.bm25_retriever.add_documents(bm25_docs)
        return upserted_count

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        top_k: int = 5,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        filters: list[MetadataFilter] | None = None,
        min_score: float | None = None,
        distance_metric: DistanceMetric | None = None,
    ) -> list[VectorSearchResult]:
        """Perform hybrid dense + sparse retrieval and merge results via RRF."""
        if not query_text and not query_vector:
            raise VectorStoreException("Either query_text or query_vector must be provided")

        # 1. Dense Vector Search
        dense_results: list[VectorSearchResult] = []
        if query_vector:
            dense_results = await self.vector_store.search(
                query_vector=query_vector,
                top_k=top_k * 2,  # Oversample for fusion
                filters=filters,
                min_score=min_score,
                distance_metric=distance_metric,
            )

        dense_ranked: list[tuple[str, float]] = [(r.id, r.score) for r in dense_results]
        dense_payload_map: dict[str, dict[str, Any]] = {r.id: r.payload for r in dense_results}
        dense_vector_map: dict[str, list[float]] = {r.id: r.vector for r in dense_results}

        # 2. Sparse BM25 Search
        sparse_ranked: list[tuple[str, float]] = []
        if query_text:
            sparse_ranked = self.bm25_retriever.search(query_text, top_k=top_k * 2)

        # 3. Reciprocal Rank Fusion
        merged_scores = self.rrf.merge(
            ranked_lists=[dense_ranked, sparse_ranked],
            weights=[dense_weight, sparse_weight],
        )

        # 4. Construct Final Results
        final_results: list[VectorSearchResult] = []
        for doc_id, score in merged_scores[:top_k]:
            payload = dense_payload_map.get(doc_id)
            vector = dense_vector_map.get(doc_id, [])

            if payload is None and doc_id in self.bm25_retriever.documents:
                payload = self.bm25_retriever.documents[doc_id].payload

            final_results.append(
                VectorSearchResult(
                    id=doc_id,
                    score=score,
                    payload=payload or {},
                    vector=vector,
                )
            )

        return final_results

    async def delete(self, ids: list[str]) -> int:
        """Delete records from vector store and BM25 index."""
        count = await self.vector_store.delete(ids)
        self.bm25_retriever.remove_documents(ids)
        return count
