import pytest

from src.adapters.mock_adapter import MockAdapter
from src.agent.agent import Agent
from src.config import RetryConfig
from src.domain.agent import AgentConfig, WorkflowStatus
from src.domain.exceptions import WorkflowException
from src.domain.models import CompletionResponse, FinishReason, TokenUsage
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.workflow import WorkflowGraph


def _make_mock_orchestrator(responses: list[CompletionResponse]) -> LLMOrchestrator:
    mock_adapter = MockAdapter(scripted_responses=responses)
    return LLMOrchestrator(
        providers={"mock": mock_adapter},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )


@pytest.mark.asyncio
async def test_agent_single_turn_execution():
    resp = CompletionResponse(
        content="Agent response content",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="req-agent-1",
    )
    llm = _make_mock_orchestrator([resp])
    agent = Agent(
        config=AgentConfig(name="test_agent", system_prompt="You are a helpful test agent."),
        orchestrator=llm,
    )

    agent_resp = await agent.run(user_input="Hello test agent")
    assert agent_resp.agent_name == "test_agent"
    assert agent_resp.message.content == "Agent response content"


@pytest.mark.asyncio
async def test_workflow_graph_sequential_and_conditional_branching():
    resp1 = CompletionResponse(
        content="Analysis complete: risk is HIGH",
        token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        latency_ms=1.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="r1",
    )
    resp2 = CompletionResponse(
        content="Escalation report generated for high risk item.",
        token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        latency_ms=1.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="mock-model",
        request_id="r2",
    )

    analyzer_llm = _make_mock_orchestrator([resp1])
    escalator_llm = _make_mock_orchestrator([resp2])

    analyzer_agent = Agent(config=AgentConfig(name="analyzer"), orchestrator=analyzer_llm)
    escalator_agent = Agent(config=AgentConfig(name="escalator"), orchestrator=escalator_llm)

    def low_risk_node(state: dict) -> dict:
        return {"result": "Logged low risk item."}

    graph = WorkflowGraph(max_steps=10)
    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("escalator", escalator_agent)
    graph.add_node("low_risk_handler", low_risk_node)

    graph.set_entry_point("analyzer")

    # Conditional edge: if risk is HIGH -> escalator, else -> low_risk_handler
    graph.add_edge("analyzer", "escalator", condition=lambda state: "HIGH" in state.get("last_output", ""))
    graph.add_edge("analyzer", "low_risk_handler", condition=lambda state: "HIGH" not in state.get("last_output", ""))

    result = await graph.run({"input": "Check risk level for account 42"})

    assert result.status == WorkflowStatus.COMPLETED
    assert len(result.history) == 2
    assert "Escalation report" in result.outputs["last_output"]


@pytest.mark.asyncio
async def test_workflow_graph_loop_safety_limit():
    def infinite_loop_node(state: dict) -> dict:
        return {"counter": state.get("counter", 0) + 1}

    graph = WorkflowGraph(max_steps=5)
    graph.add_node("loop_node", infinite_loop_node)
    graph.set_entry_point("loop_node")
    graph.add_edge("loop_node", "loop_node")  # Cycle back to self

    result = await graph.run({"counter": 0})
    assert result.status == WorkflowStatus.FAILED
    assert "exceeded maximum safety steps limit" in result.error
