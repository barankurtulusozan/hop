import pytest
from src.adapters.mock_adapter import MockAdapter
from src.config import RetryConfig
from src.domain.models import CompletionRequest, CompletionResponse, FinishReason, Message, Role, TokenUsage
from src.domain.tools import ToolCall
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.tool_runner import ToolOrchestrator
from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry


def add_numbers(a: int, b: int) -> int:
    return a + b


@pytest.mark.asyncio
async def test_tool_orchestrator_successful_tool_call_and_response_flow():
    registry = ToolRegistry()
    registry.register_function(add_numbers, name="add_numbers", description="Add two numbers")
    executor = ToolExecutor(registry)

    # 1st LLM call returns a tool_call request
    # 2nd LLM call returns the final text response after seeing tool output
    resp1 = CompletionResponse(
        content="I will add these numbers for you.",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        latency_ms=5.0,
        finish_reason=FinishReason.TOOL_CALLS,
        provider="mock",
        model="mock-model",
        request_id="req-1",
        tool_calls=[ToolCall(call_id="call-1", tool_name="add_numbers", arguments={"a": 15, "b": 25})],
    )
    resp2 = CompletionResponse(
        content="The sum of 15 and 25 is 40.",
        token_usage=TokenUsage(prompt_tokens=20, completion_tokens=10),
        latency_ms=5.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="req-2",
    )

    mock_adapter = MockAdapter(scripted_responses=[resp1, resp2])
    llm = LLMOrchestrator(
        providers={"mock": mock_adapter},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    tool_orch = ToolOrchestrator(llm, executor)
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="What is 15 + 25?")],
        model="mock-model",
        tools=registry.list_tools(),
    )

    final_resp, tool_results = await tool_orch.run_with_tools(req)

    assert len(tool_results) == 1
    assert tool_results[0].result == 40
    assert tool_results[0].is_error is False
    assert final_resp.content == "The sum of 15 and 25 is 40."


@pytest.mark.asyncio
async def test_tool_orchestrator_auto_corrects_malformed_tool_call():
    registry = ToolRegistry()
    registry.register_function(add_numbers, name="add_numbers", description="Add two numbers")
    executor = ToolExecutor(registry)

    # 1st LLM call returns invalid args ("bad" string instead of int)
    resp1 = CompletionResponse(
        content="",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        latency_ms=5.0,
        finish_reason=FinishReason.TOOL_CALLS,
        provider="mock",
        model="mock-model",
        request_id="req-1",
        tool_calls=[ToolCall(call_id="call-bad", tool_name="add_numbers", arguments={"a": "bad", "b": 10})],
    )
    # 2nd LLM call receives error turn and provides corrected arguments
    resp2 = CompletionResponse(
        content="",
        token_usage=TokenUsage(prompt_tokens=15, completion_tokens=5),
        latency_ms=5.0,
        finish_reason=FinishReason.TOOL_CALLS,
        provider="mock",
        model="mock-model",
        request_id="req-2",
        tool_calls=[ToolCall(call_id="call-good", tool_name="add_numbers", arguments={"a": 5, "b": 10})],
    )
    # 3rd LLM call returns final answer after successful execution
    resp3 = CompletionResponse(
        content="The result is 15.",
        token_usage=TokenUsage(prompt_tokens=25, completion_tokens=10),
        latency_ms=5.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="req-3",
    )

    mock_adapter = MockAdapter(scripted_responses=[resp1, resp2, resp3])
    llm = LLMOrchestrator(
        providers={"mock": mock_adapter},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    tool_orch = ToolOrchestrator(llm, executor, max_tool_retries=2)
    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="Calculate 5 + 10")],
        model="mock-model",
        tools=registry.list_tools(),
    )

    final_resp, tool_results = await tool_orch.run_with_tools(req)

    assert len(tool_results) == 2
    assert tool_results[0].is_error is True
    assert "Validation failed" in tool_results[0].error
    assert tool_results[1].is_error is False
    assert tool_results[1].result == 15
    assert final_resp.content == "The result is 15."
