import pytest
from src.domain.vector import DistanceMetric, VectorRecord
from src.vector.hybrid import (
    BM25Document,
    BM25Retriever,
    HybridVectorStore,
    ReciprocalRankFusion,
    tokenize,
)
from src.vector.store import InMemoryVectorStore


def test_tokenize():
    text = "Hello World! This is an AI LLM Orchestrator."
    tokens = tokenize(text)
    assert tokens == ["hello", "world", "this", "is", "an", "ai", "llm", "orchestrator"]


def test_bm25_retriever_basic():
    retriever = BM25Retriever()
    docs = [
        BM25Document(id="doc1", content="Python enterprise microservice framework"),
        BM25Document(id="doc2", content="Golang cloud native high concurrency engine"),
        BM25Document(id="doc3", content="Python vector store and RAG pipeline engine"),
    ]
    retriever.add_documents(docs)

    assert retriever.corpus_size == 3
    results = retriever.search("Python RAG", top_k=2)
    assert len(results) == 2
    assert results[0][0] in ["doc3", "doc1"]


def test_reciprocal_rank_fusion():
    rrf = ReciprocalRankFusion(rrf_k=60)
    dense_list = [("doc1", 0.95), ("doc2", 0.85), ("doc3", 0.75)]
    sparse_list = [("doc3", 5.2), ("doc1", 3.1), ("doc4", 1.8)]

    merged = rrf.merge([dense_list, sparse_list], weights=[0.5, 0.5])
    doc_ids = [m[0] for m in merged]
    assert "doc1" in doc_ids
    assert "doc3" in doc_ids


@pytest.mark.asyncio
async def test_hybrid_vector_store_upsert_and_search():
    base_store = InMemoryVectorStore(default_metric=DistanceMetric.COSINE)
    hybrid_store = HybridVectorStore(vector_store=base_store)

    records = [
        VectorRecord(
            id="vec1",
            vector=[1.0, 0.0, 0.0],
            payload={"content": "Enterprise AI Security Policy and PBAC Governance"},
        ),
        VectorRecord(
            id="vec2",
            vector=[0.0, 1.0, 0.0],
            payload={"content": "Streaming SSE Gateway and Async Queue System"},
        ),
        VectorRecord(
            id="vec3",
            vector=[0.5, 0.5, 0.0],
            payload={"content": "RAG Dense Vector Search and Hybrid Retrieval"},
        ),
    ]

    count = await hybrid_store.upsert(records)
    assert count == 3

    # Perform hybrid search
    results = await hybrid_store.hybrid_search(
        query_text="RAG Vector Hybrid",
        query_vector=[0.5, 0.5, 0.0],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].id == "vec3"


@pytest.mark.asyncio
async def test_hybrid_vector_store_delete():
    base_store = InMemoryVectorStore()
    hybrid_store = HybridVectorStore(vector_store=base_store)

    records = [
        VectorRecord(id="rec1", vector=[1.0, 0.0], payload={"text": "Doc 1"}),
        VectorRecord(id="rec2", vector=[0.0, 1.0], payload={"text": "Doc 2"}),
    ]
    await hybrid_store.upsert(records)

    deleted = await hybrid_store.delete(["rec1"])
    assert deleted == 1

    results = await hybrid_store.hybrid_search(query_text="Doc 1", query_vector=[1.0, 0.0], top_k=5)
    assert all(r.id != "rec1" for r in results)
