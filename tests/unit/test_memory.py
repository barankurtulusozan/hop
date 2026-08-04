import pytest

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.adapters.mock_adapter import MockAdapter
from src.domain.memory import MemoryStrategy
from src.domain.models import CompletionResponse, FinishReason, Message, Role, TokenUsage
from src.memory.manager import MemoryManager
from src.orchestrator.pipeline import LLMOrchestrator
from src.vector.pipeline import DenseRetriever, VectorIngestionPipeline
from src.vector.store import InMemoryVectorStore
from src.domain.vector import Document


@pytest.mark.asyncio
async def test_memory_manager_sliding_window():
    manager = MemoryManager(strategy=MemoryStrategy.SLIDING_WINDOW, max_window_size=2)
    session_id = "test_sess_1"

    await manager.add_turn(session_id, Message(role=Role.USER, content="Hello 1"))
    await manager.add_turn(session_id, Message(role=Role.ASSISTANT, content="Hi 1"))
    await manager.add_turn(session_id, Message(role=Role.USER, content="Hello 2"))
    await manager.add_turn(session_id, Message(role=Role.ASSISTANT, content="Hi 2"))

    msgs = await manager.get_messages(session_id)
    assert len(msgs) == 2
    assert msgs[0].content == "Hello 2"
    assert msgs[1].content == "Hi 2"


@pytest.mark.asyncio
async def test_memory_manager_token_budget():
    manager = MemoryManager(strategy=MemoryStrategy.TOKEN_BUDGET, max_token_budget=20)
    session_id = "test_sess_2"

    await manager.add_turn(session_id, Message(role=Role.USER, content="Short msg"), system_prompt="System rules")
    await manager.add_turn(session_id, Message(role=Role.ASSISTANT, content="A very very very very long message that consumes token budget."))

    msgs = await manager.get_messages(session_id)
    assert msgs[0].role == Role.SYSTEM
    assert msgs[0].content == "System rules"
    # Should contain system message + trimmed message
    assert len(msgs) >= 1


@pytest.mark.asyncio
async def test_memory_manager_summarized_strategy():
    summary_resp = CompletionResponse(
        content="User greeted assistant, assistant acknowledged.",
        token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="summary-1",
    )
    from src.config import RetryConfig

    mock_llm = MockAdapter(scripted_responses=[summary_resp])
    orchestrator = LLMOrchestrator(
        providers={"mock": mock_llm},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    manager = MemoryManager(
        strategy=MemoryStrategy.SUMMARIZED,
        max_window_size=2,
        orchestrator=orchestrator,
    )
    session_id = "test_sess_sum"

    await manager.add_turn(session_id, Message(role=Role.USER, content="Turn 1"))
    await manager.add_turn(session_id, Message(role=Role.ASSISTANT, content="Turn 2"))

    # Turn 3 triggers auto-summarization because turns (3) > max_window_size (2)
    await manager.add_turn(session_id, Message(role=Role.USER, content="Turn 3"))

    msgs = await manager.get_messages(session_id)
    assert any("Prior Conversation Summary" in m.content for m in msgs)


@pytest.mark.asyncio
async def test_memory_manager_hybrid_vector():
    embedding_provider = MockEmbeddingAdapter(dimension=64)
    vector_store = InMemoryVectorStore()
    pipeline = VectorIngestionPipeline(embedding_provider, vector_store)
    retriever = DenseRetriever(embedding_provider, vector_store)

    await pipeline.ingest_documents([
        Document(id="doc_mem_1", content="User prefers Python over JavaScript for backend services.")
    ])

    manager = MemoryManager(
        strategy=MemoryStrategy.HYBRID_VECTOR,
        retriever=retriever,
        max_token_budget=100,
    )
    session_id = "test_sess_hybrid"

    await manager.add_turn(session_id, Message(role=Role.USER, content="What language do I prefer?"))

    msgs = await manager.get_messages(session_id, query="Python backend preference")
    assert any("Relevant Memory Context" in m.content for m in msgs)
