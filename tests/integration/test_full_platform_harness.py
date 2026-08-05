import pytest

from src.adapters.mock_adapter import MockAdapter
from src.config import RetryConfig
from src.domain.models import CompletionResponse, FinishReason, TokenUsage
from src.domain.security import Permission, RateLimitTier, Role, TenantContext
from src.evals.evaluator import ShadowEvaluator
from src.harness.harness import PlatformIntegrationHarness
from src.observability.cost_guard import CostGuardrail
from src.observability.safety import SafetyGuardrail
from src.observability.tracer import Tracer
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.router import DynamicProviderRouter
from src.security.auth import TokenAuthenticator
from src.security.policy import PolicyEngine
from src.security.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_full_platform_integration_harness():
    # 1. Security & Auth Setup
    auth = TokenAuthenticator()
    policy = PolicyEngine()
    rate_limiter = TokenBucketRateLimiter()

    ctx = TenantContext(
        tenant_id="enterprise_org_99",
        user_id="alice_dev",
        roles=[Role.DEVELOPER],
        permissions=[Permission.AGENT_RUN, Permission.TOOL_INVOKE],
        tier=RateLimitTier.ENTERPRISE,
    )
    auth.register_token("ent_token_sec_999", ctx)

    # 2. Governance & Observability Setup
    cost_guard = CostGuardrail()
    safety_guard = SafetyGuardrail()
    tracer = Tracer()
    evaluator = ShadowEvaluator()

    # 3. Router Setup
    mock_resp = CompletionResponse(
        content="Platform verification passed cleanly.",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        latency_ms=2.5,
        finish_reason=FinishReason.STOP,
        provider="mock",
        model="gpt-4o",
        request_id="req-harness-1",
    )
    mock_provider = MockAdapter(scripted_responses=[mock_resp])
    orch = LLMOrchestrator(
        providers={"mock": mock_provider},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=1, initial_delay_seconds=0.001, jitter=False),
    )

    router = DynamicProviderRouter(providers={"mock": orch})

    # 4. Initialize Platform Integration Harness
    harness = PlatformIntegrationHarness(
        authenticator=auth,
        policy_engine=policy,
        rate_limiter=rate_limiter,
        cost_guard=cost_guard,
        safety_guard=safety_guard,
        tracer=tracer,
        router=router,
        evaluator=evaluator,
    )

    # 5. Execute End-to-End Verification Pipeline
    raw_prompt = "Process request for john@company.com with key sk-proj-1234567890abcdef12345678."
    res = await harness.execute_request(
        token="Bearer ent_token_sec_999",
        user_input=raw_prompt,
        model="gpt-4o",
    )

    assert res["tenant_id"] == "enterprise_org_99"
    assert res["user_id"] == "alice_dev"
    assert res["agent_output"] == "Platform verification passed cleanly."
    assert res["redacted_items_count"] == 2
    assert res["cost_usd"] > 0
    assert res["eval_passed"] is True
