import pytest
from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.adapters.mock_adapter import MockAdapter
from src.domain.models import CompletionRequest, CompletionResponse, FinishReason, Message, Role, TokenUsage
from src.domain.tools import ToolCall
from src.domain.vector import Document, MetadataFilter, FilterOperator
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.tool_runner import ToolOrchestrator
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry
from src.vector.chunker import RecursiveCharacterTextSplitter
from src.vector.pipeline import DenseRetriever, VectorIngestionPipeline
from src.vector.store import InMemoryVectorStore
from src.vector.tool import create_vector_search_tool


@pytest.mark.asyncio
async def test_end_to_end_rag_ingestion_and_retrieval():
    embedding_provider = MockEmbeddingAdapter(dimension=64)
    vector_store = InMemoryVectorStore()
    splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)

    pipeline = VectorIngestionPipeline(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        text_splitter=splitter,
    )
    retriever = DenseRetriever(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    doc1 = Document(
        id="doc_arch",
        content="Hexagonal architecture decouples domain logic from vendor SDKs via ports and adapters.",
        metadata={"category": "architecture"},
    )
    doc2 = Document(
        id="doc_resilience",
        content="Resilience features include exponential backoff with full jitter and circuit breakers.",
        metadata={"category": "resilience"},
    )

    ingested = await pipeline.ingest_documents([doc1, doc2])
    assert len(ingested) >= 2
    assert await vector_store.count() == len(ingested)

    # Dense retrieval query
    results = await retriever.retrieve(query="What is hexagonal architecture?", top_k=2)
    assert len(results) >= 1
    assert any("Hexagonal architecture" in res.payload.get("text", "") for res in results)

    # Retrieval with filter
    filter_resilience = [MetadataFilter(field="category", operator=FilterOperator.EQ, value="resilience")]
    filtered_results = await retriever.retrieve(
        query="circuit breakers", top_k=5, filters=filter_resilience
    )
    assert len(filtered_results) == 1
    assert filtered_results[0].payload["category"] == "resilience"


@pytest.mark.asyncio
async def test_rag_tool_orchestrator_integration():
    embedding_provider = MockEmbeddingAdapter(dimension=64)
    vector_store = InMemoryVectorStore()
    pipeline = VectorIngestionPipeline(embedding_provider, vector_store)
    retriever = DenseRetriever(embedding_provider, vector_store)

    doc = Document(
        id="policy_01",
        content="Enterprise SLA requirement specifies 99.99% uptime with 50ms p99 latency.",
        metadata={"dept": "ops"},
    )
    await pipeline.ingest_documents([doc])

    # Register vector search tool
    registry = ToolRegistry()
    tool_name, tool_desc, tool_fn = create_vector_search_tool(retriever)
    registry.register_function(tool_fn, name=tool_name, description=tool_desc)

    tool_executor = ToolExecutor(registry)

    # Mock LLM adapter that returns tool call first turn, then final answer second turn
    resp1 = CompletionResponse(
        content="",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        latency_ms=2.0,
        finish_reason=FinishReason.TOOL_CALLS,
        provider="mock",
        model="mock-model",
        request_id="req-1",
        tool_calls=[
            ToolCall(
                call_id="call_rag_1",
                tool_name="search_knowledge_base",
                arguments={"query": "SLA requirement uptime", "top_k": 1},
            )
        ],
    )
    resp2 = CompletionResponse(
        content="The enterprise SLA requirement specifies 99.99% uptime.",
        token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="req-2",
    )

    from src.config import RetryConfig

    mock_llm = MockAdapter(scripted_responses=[resp1, resp2])
    orchestrator = LLMOrchestrator(
        providers={"mock": mock_llm},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )
    tool_orch = ToolOrchestrator(orchestrator, tool_executor)

    request = CompletionRequest(
        messages=[Message(role=Role.USER, content="What is the SLA requirement?")],
        model="mock-model",
        tools=registry.list_tools(),
    )

    final_resp, tool_results = await tool_orch.run_with_tools(request)
    assert final_resp.content == "The enterprise SLA requirement specifies 99.99% uptime."
    assert len(tool_results) == 1
    assert tool_results[0].call_id == "call_rag_1"
    assert tool_results[0].error is None
    assert "99.99% uptime" in str(tool_results[0].result)

