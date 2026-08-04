from __future__ import annotations

from typing import Sequence

from src.domain.interfaces import EmbeddingProvider, VectorStore
from src.domain.vector import (
    DistanceMetric,
    Document,
    EmbeddingRequest,
    MetadataFilter,
    VectorRecord,
    VectorSearchResult,
    Chunk,
)
from src.vector.chunker import RecursiveCharacterTextSplitter


class VectorIngestionPipeline:
    """Pipeline for document chunking, embedding generation, and vector store indexing."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        text_splitter: RecursiveCharacterTextSplitter | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.text_splitter = text_splitter or RecursiveCharacterTextSplitter()

    async def ingest_documents(self, documents: list[Document]) -> list[Chunk]:
        if not documents:
            return []

        all_chunks: list[Chunk] = []
        for doc in documents:
            doc_chunks = self.text_splitter.split_document(doc)
            all_chunks.extend(doc_chunks)

        if not all_chunks:
            return []

        # Generate embeddings in batch for all chunks
        chunk_texts = [c.text for c in all_chunks]
        emb_request = EmbeddingRequest(input_texts=chunk_texts)
        emb_response = await self.embedding_provider.embed(emb_request)

        records: list[VectorRecord] = []
        for chunk, vector in zip(all_chunks, emb_response.embeddings):
            payload = dict(chunk.metadata)
            payload["text"] = chunk.text
            records.append(
                VectorRecord(
                    id=chunk.id,
                    vector=vector,
                    payload=payload,
                )
            )

        await self.vector_store.upsert(records)
        return all_chunks


class DenseRetriever:
    """Dense semantic retriever executing query embedding and top-k vector search."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        default_top_k: int = 5,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.default_top_k = default_top_k

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: list[MetadataFilter] | None = None,
        min_score: float | None = None,
        distance_metric: DistanceMetric | None = None,
    ) -> list[VectorSearchResult]:
        if not query.strip():
            return []

        k = top_k if top_k is not None else self.default_top_k

        emb_request = EmbeddingRequest(input_texts=[query])
        emb_response = await self.embedding_provider.embed(emb_request)
        query_vector = emb_response.embeddings[0]

        return await self.vector_store.search(
            query_vector=query_vector,
            top_k=k,
            filters=filters,
            min_score=min_score,
            distance_metric=distance_metric,
        )
