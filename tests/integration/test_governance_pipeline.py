import pytest

from src.adapters.mock_adapter import MockAdapter
from src.agent.agent import Agent
from src.config import RetryConfig
from src.domain.agent import AgentConfig
from src.domain.evals import TestCase
from src.domain.models import CompletionResponse, FinishReason, TokenUsage
from src.domain.observability import CostLimit, SpanKind
from src.evals.evaluator import ShadowEvaluator
from src.observability.cost_guard import CostGuardrail
from src.observability.safety import SafetyGuardrail
from src.observability.tracer import Tracer
from src.orchestrator.pipeline import LLMOrchestrator


@pytest.mark.asyncio
async def test_end_to_end_governance_pipeline():
    tenant_id = "enterprise_tenant_01"
    tracer = Tracer()
    cost_guard = CostGuardrail()
    safety = SafetyGuardrail()
    evaluator = ShadowEvaluator()

    await cost_guard.set_limit(
        tenant_id,
        CostLimit(tenant_id=tenant_id, max_daily_budget_usd=10.0, max_tokens_per_minute=10000),
    )

    # 1. Input prompt with PII email
    user_input = "Contact support@enterprise.com regarding API key sk-proj-1234567890abcdef12345678."

    # 2. Safety Check & PII Redaction
    safety_res = safety.check_text(user_input)
    assert safety_res.is_safe is True
    assert safety_res.redacted_items_count == 2
    sanitized_prompt = safety_res.sanitized_text

    # 3. LLM Orchestrator setup
    resp = CompletionResponse(
        content="Support ticket created for redacted email.",
        token_usage=TokenUsage(prompt_tokens=15, completion_tokens=10),
        latency_ms=3.0,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="gpt-4o",
        request_id="req-gov-1",
    )
    llm = LLMOrchestrator(
        providers={"mock": MockAdapter(scripted_responses=[resp])},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    agent = Agent(
        config=AgentConfig(name="governance_agent", system_prompt="You are a compliant support agent.", model="gpt-4o"),
        orchestrator=llm,
    )

    # 4. Tracing & Agent Run
    async with tracer.span(name="agent_governance_run", kind=SpanKind.AGENT_TURN) as span:
        agent_resp = await agent.run(user_input=sanitized_prompt)

        # Record Cost Usage
        cost = await cost_guard.check_and_record_usage(
            tenant_id=tenant_id,
            model="gpt-4o",
            prompt_tokens=resp.token_usage.prompt_tokens,
            completion_tokens=resp.token_usage.completion_tokens,
        )
        assert cost > 0

    spans = await tracer.export_spans(trace_id=span.trace_id)
    assert len(spans) == 1
    assert spans[0].duration_ms is not None

    # 5. Shadow Evaluation
    tc = TestCase(
        test_case_id="tc_gov_01",
        input=user_input,
        expected_output="Support ticket created for redacted email.",
    )
    eval_res = await evaluator.evaluate_test_case(
        test_case=tc,
        actual_output=agent_resp.message.content,
        latency_ms=spans[0].duration_ms or 0.0,
    )

    assert eval_res.passed is True
    assert eval_res.score >= 0.9
