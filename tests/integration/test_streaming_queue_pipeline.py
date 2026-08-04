import asyncio
import pytest

from src.adapters.mock_adapter import MockAdapter
from src.agent.agent import Agent
from src.config import RetryConfig
from src.domain.agent import AgentConfig
from src.domain.models import FinishReason, StreamChunk, TokenUsage
from src.domain.queue import TaskPriority, TaskStatus
from src.domain.router import RoutingStrategy
from src.gateway.streaming import SSEStreamFormatter
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.router import DynamicProviderRouter
from src.queue.engine import AsyncTaskQueue


@pytest.mark.asyncio
async def test_end_to_end_queue_router_and_streaming_pipeline():
    # 1. Setup providers and DynamicProviderRouter
    resp_primary = StreamChunk(delta="Streamed ", is_final=False)
    resp_final = StreamChunk(
        delta="output payload",
        is_final=True,
        finish_reason=FinishReason.STOP,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
    )

    mock_llm_primary = MockAdapter(response_content="Streamed output payload")
    orch_primary = LLMOrchestrator(
        providers={"mock": mock_llm_primary},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    router = DynamicProviderRouter(
        providers={"primary": orch_primary},
        strategy=RoutingStrategy.PRIORITY_FALLBACK,
    )

    agent = Agent(
        config=AgentConfig(name="pipeline_agent", system_prompt="You are a streaming pipeline agent."),
        orchestrator=orch_primary,
    )

    # 2. Setup AsyncTaskQueue with handler
    task_queue = AsyncTaskQueue()

    async def handle_agent_job(payload: dict) -> dict:
        prompt = payload["prompt"]
        agent_resp = await agent.run(user_input=prompt)
        return {"agent_output": agent_resp.message.content}

    task_queue.register_handler("agent_job", handle_agent_job)

    # 3. Enqueue and process task
    task = await task_queue.enqueue("agent_job", {"prompt": "Run streaming task"}, priority=TaskPriority.HIGH)
    task_queue.start_workers(num_workers=1)

    await asyncio.sleep(0.15)
    await task_queue.stop_workers()

    processed_task = await task_queue.get_task(task.task_id)
    assert processed_task is not None
    assert processed_task.status == TaskStatus.COMPLETED
    assert "Streamed output payload" in processed_task.result["agent_output"]

    # 4. SSE Stream Formatter verification
    formatter = SSEStreamFormatter()

    async def mock_stream():
        yield resp_primary
        yield resp_final

    sse_events: list[str] = []
    async for sse_chunk in formatter.format_stream(mock_stream()):
        sse_events.append(sse_chunk)

    assert len(sse_events) >= 2
    assert "event: chunk" in sse_events[0]
    assert "event: done" in sse_events[-1]
