import pytest

from src.adapters.embeddings.mock_adapter import MockEmbeddingAdapter
from src.adapters.mock_adapter import MockAdapter
from src.agent.agent import Agent
from src.config import RetryConfig
from src.domain.agent import AgentConfig, WorkflowStatus
from src.domain.models import CompletionResponse, FinishReason, TokenUsage
from src.domain.tools import ToolCall
from src.domain.vector import Document
from src.memory.manager import MemoryManager
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.workflow import WorkflowGraph
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry
from src.vector.pipeline import DenseRetriever, VectorIngestionPipeline
from src.vector.store import InMemoryVectorStore
from src.vector.tool import create_vector_search_tool


@pytest.mark.asyncio
async def test_end_to_end_multi_agent_rag_and_memory_workflow():
    # 1. Setup Phase 3 Dense RAG Vector Pipeline
    embedding_provider = MockEmbeddingAdapter(dimension=64)
    vector_store = InMemoryVectorStore()
    ingestion_pipeline = VectorIngestionPipeline(embedding_provider, vector_store)
    retriever = DenseRetriever(embedding_provider, vector_store)

    await ingestion_pipeline.ingest_documents([
        Document(
            id="policy_security",
            content="Platform Security Policy: All external API keys must be encrypted with AES-256-GCM.",
            metadata={"domain": "security"},
        )
    ])

    # 2. Setup Tool Registry with RAG search tool
    registry = ToolRegistry()
    tool_name, tool_desc, tool_fn = create_vector_search_tool(retriever)
    registry.register_function(tool_fn, name=tool_name, description=tool_desc)
    tool_executor = ToolExecutor(registry)

    # 3. Setup Mock LLMs for ResearcherAgent and SummarizerAgent
    resp_researcher_tool = CompletionResponse(
        content="",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        latency_ms=2.0,
        finish_reason=FinishReason.TOOL_CALLS,
        provider="mock",
        model="mock-model",
        request_id="r_tool",
        tool_calls=[
            ToolCall(
                call_id="call_rag_sec",
                tool_name="search_knowledge_base",
                arguments={"query": "security policy API keys", "top_k": 1},
            )
        ],
    )
    resp_researcher_final = CompletionResponse(
        content="Research finding: API keys must be encrypted using AES-256-GCM.",
        token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="r_final",
    )

    resp_summarizer_final = CompletionResponse(
        content="Executive Summary: Platform security mandates AES-256-GCM encryption for all external API keys.",
        token_usage=TokenUsage(prompt_tokens=15, completion_tokens=15),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="s_final",
    )

    researcher_llm = LLMOrchestrator(
        providers={"mock": MockAdapter(scripted_responses=[resp_researcher_tool, resp_researcher_final])},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    summarizer_llm = LLMOrchestrator(
        providers={"mock": MockAdapter(scripted_responses=[resp_summarizer_final])},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    # 4. Setup Agents with MemoryManager
    memory_manager = MemoryManager()

    researcher_agent = Agent(
        config=AgentConfig(name="researcher", system_prompt="You are a security researcher agent."),
        orchestrator=researcher_llm,
        tool_executor=tool_executor,
        memory_manager=memory_manager,
    )

    summarizer_agent = Agent(
        config=AgentConfig(name="summarizer", system_prompt="You are an executive summarizer agent."),
        orchestrator=summarizer_llm,
        memory_manager=memory_manager,
    )

    # 5. Build WorkflowGraph (ResearcherAgent -> SummarizerAgent)
    graph = WorkflowGraph()
    graph.add_node("researcher", researcher_agent)
    graph.add_node("summarizer", summarizer_agent)
    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "summarizer")

    # 6. Execute Multi-Agent Workflow
    result = await graph.run({"input": "What is the platform security policy regarding API keys?"})

    assert result.status == WorkflowStatus.COMPLETED
    assert len(result.history) == 2
    assert result.history[0].agent_name == "researcher"
    assert result.history[1].agent_name == "summarizer"
    assert "AES-256-GCM encryption" in result.outputs["last_output"]
