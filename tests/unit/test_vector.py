import pytest
import pytest_asyncio

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.adapters.embeddings.openai_adapter import OpenAIEmbeddingAdapter
from src.domain.exceptions import (
    ChunkingException,
    EmbeddingException,
    VectorStoreException,
)
from src.domain.vector import (
    DistanceMetric,
    Document,
    EmbeddingRequest,
    FilterOperator,
    MetadataFilter,
    VectorRecord,
)
from src.vector.chunker import RecursiveCharacterTextSplitter
from src.vector.store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_mock_embedding_adapter():
    adapter = MockEmbeddingAdapter(dimension=128)
    assert adapter.dimension == 128

    req = EmbeddingRequest(input_texts=["hello world", "foo bar"])
    res = await adapter.embed(req)

    assert len(res.embeddings) == 2
    assert len(res.embeddings[0]) == 128
    assert res.token_usage.prompt_tokens > 0
    # Deterministic check: same text gives same vector
    res2 = await adapter.embed(EmbeddingRequest(input_texts=["hello world"]))
    assert res.embeddings[0] == res2.embeddings[0]


@pytest.mark.asyncio
async def test_in_memory_vector_store_crud_and_metrics():
    store = InMemoryVectorStore(default_metric=DistanceMetric.COSINE)
    assert await store.count() == 0

    rec1 = VectorRecord(id="1", vector=[1.0, 0.0, 0.0], payload={"category": "tech", "val": 10})
    rec2 = VectorRecord(id="2", vector=[0.0, 1.0, 0.0], payload={"category": "finance", "val": 20})
    rec3 = VectorRecord(id="3", vector=[0.7071, 0.7071, 0.0], payload={"category": "tech", "val": 30})

    upserted = await store.upsert([rec1, rec2, rec3])
    assert upserted == 3
    assert await store.count() == 3

    # Cosine search for [1.0, 0.0, 0.0]
    results = await store.search(query_vector=[1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0].id == "1"
    assert pytest.approx(results[0].score, 0.001) == 1.0
    assert results[1].id == "3"
    assert pytest.approx(results[1].score, 0.001) == 0.7071

    # Dot Product metric
    results_dp = await store.search(query_vector=[1.0, 0.0, 0.0], top_k=2, distance_metric=DistanceMetric.DOT_PRODUCT)
    assert results_dp[0].id == "1"
    assert pytest.approx(results_dp[0].score, 0.001) == 1.0

    # Euclidean metric
    results_l2 = await store.search(query_vector=[1.0, 0.0, 0.0], top_k=2, distance_metric=DistanceMetric.EUCLIDEAN)
    assert results_l2[0].id == "1"
    assert pytest.approx(results_l2[0].score, 0.001) == 1.0

    # Delete record
    deleted = await store.delete(["2"])
    assert deleted == 1
    assert await store.count() == 2


@pytest.mark.asyncio
async def test_vector_store_metadata_filtering():
    store = InMemoryVectorStore()
    rec1 = VectorRecord(id="1", vector=[1.0, 0.0], payload={"category": "tech", "score": 90, "tags": ["ai", "ml"]})
    rec2 = VectorRecord(id="2", vector=[0.9, 0.1], payload={"category": "tech", "score": 50, "tags": ["web"]})
    rec3 = VectorRecord(id="3", vector=[0.8, 0.2], payload={"category": "finance", "score": 95, "tags": ["stocks"]})
    await store.upsert([rec1, rec2, rec3])

    # Filter eq category tech AND gt score 70
    filters = [
        MetadataFilter(field="category", operator=FilterOperator.EQ, value="tech"),
        MetadataFilter(field="score", operator=FilterOperator.GT, value=70),
    ]
    results = await store.search(query_vector=[1.0, 0.0], filters=filters)
    assert len(results) == 1
    assert results[0].id == "1"

    # Filter contains tag
    filters_contains = [MetadataFilter(field="tags", operator=FilterOperator.CONTAINS, value="ai")]
    results_contains = await store.search(query_vector=[1.0, 0.0], filters=filters_contains)
    assert len(results_contains) == 1
    assert results_contains[0].id == "1"

    # Filter IN
    filters_in = [MetadataFilter(field="category", operator=FilterOperator.IN, value=["finance", "other"])]
    results_in = await store.search(query_vector=[1.0, 0.0], filters=filters_in)
    assert len(results_in) == 1
    assert results_in[0].id == "3"


@pytest.mark.asyncio
async def test_vector_store_validation_and_edge_cases():
    store = InMemoryVectorStore()
    await store.upsert([VectorRecord(id="1", vector=[1.0, 0.0])])

    with pytest.raises(VectorStoreException, match="Dimension mismatch"):
        await store.search(query_vector=[1.0, 0.0, 0.0])

    with pytest.raises(VectorStoreException, match="cannot be empty"):
        await store.search(query_vector=[])

    with pytest.raises(VectorStoreException, match="empty vector"):
        await store.upsert([VectorRecord(id="bad", vector=[])])


def test_recursive_character_text_splitter():
    splitter = RecursiveCharacterTextSplitter(chunk_size=50, chunk_overlap=10)
    text = "Paragraph one with detailed content.\n\nParagraph two with additional statements."

    chunks = splitter.split_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 60  # Allows slight boundary buffer depending on separators

    doc = Document(id="doc_100", content=text, metadata={"source": "unittest"})
    doc_chunks = splitter.split_document(doc)
    assert len(doc_chunks) > 1
    assert doc_chunks[0].doc_id == "doc_100"
    assert doc_chunks[0].metadata["source"] == "unittest"
    assert doc_chunks[0].chunk_index == 0


def test_splitter_invalid_args():
    with pytest.raises(ChunkingException, match="chunk_size must be > 0"):
        RecursiveCharacterTextSplitter(chunk_size=0)

    with pytest.raises(ChunkingException, match="chunk_overlap.*strictly less"):
        RecursiveCharacterTextSplitter(chunk_size=50, chunk_overlap=50)
