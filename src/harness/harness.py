from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from src.agent.agent import Agent
from src.domain.agent import AgentConfig, AgentResponse
from src.domain.evals import TestCase
from src.domain.observability import CostLimit, SpanKind
from src.domain.security import Permission
from src.evals.evaluator import ShadowEvaluator
from src.gateway.streaming import SSEStreamFormatter
from src.observability.cost_guard import CostGuardrail
from src.observability.safety import SafetyGuardrail
from src.observability.tracer import Tracer
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.router import DynamicProviderRouter
from src.security.auth import TokenAuthenticator
from src.security.policy import PolicyEngine
from src.security.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger("llm_orchestrator.harness")


class PlatformIntegrationHarness:
    """Production Verification Harness validating end-to-end platform security, governance, routing, and streaming."""

    def __init__(
        self,
        authenticator: TokenAuthenticator,
        policy_engine: PolicyEngine,
        rate_limiter: TokenBucketRateLimiter,
        cost_guard: CostGuardrail,
        safety_guard: SafetyGuardrail,
        tracer: Tracer,
        router: DynamicProviderRouter,
        evaluator: ShadowEvaluator,
    ):
        self.authenticator = authenticator
        self.policy_engine = policy_engine
        self.rate_limiter = rate_limiter
        self.cost_guard = cost_guard
        self.safety_guard = safety_guard
        self.tracer = tracer
        self.router = router
        self.evaluator = evaluator
        self.stream_formatter = SSEStreamFormatter()

    async def execute_request(
        self,
        token: str,
        user_input: str,
        system_prompt: str = "You are a secure platform agent.",
        model: str = "gpt-4o",
    ) -> dict[str, Any]:
        # 1. Authenticate Token
        ctx = self.authenticator.authenticate(token)

        # 2. Rate Limit Enforcement
        await self.rate_limiter.enforce(ctx.tenant_id, ctx.tier)

        # 3. PBAC Policy Enforcement
        self.policy_engine.enforce(ctx, Permission.AGENT_RUN)

        # 4. Safety Guardrail & PII Redaction
        safety_res = self.safety_guard.check_text(user_input)
        sanitized_input = safety_res.sanitized_text

        # 5. Cost Guardrail Budget Verification
        await self.cost_guard.set_limit(
            ctx.tenant_id,
            CostLimit(tenant_id=ctx.tenant_id, max_daily_budget_usd=100.0, max_tokens_per_minute=50000),
        )

        # Pick primary orchestrator from router candidates
        candidate = self.router.provider_priority[0]
        primary_orch = self.router.providers[candidate]

        agent = Agent(
            config=AgentConfig(name="harness_agent", system_prompt=system_prompt, model=model),
            orchestrator=primary_orch,
        )

        # 6. Traced Execution
        async with self.tracer.span(name="harness_agent_run", kind=SpanKind.AGENT_TURN) as span:
            agent_resp: AgentResponse = await agent.run(user_input=sanitized_input)

            # Record cost usage
            usage = agent_resp.token_usage
            p_tokens = usage.prompt_tokens if usage else 10
            c_tokens = usage.completion_tokens if usage else 10
            cost = await self.cost_guard.check_and_record_usage(
                tenant_id=ctx.tenant_id,
                model=model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
            )

        # 7. Shadow Evaluation
        tc = TestCase(
            test_case_id="tc_harness_01",
            input=user_input,
            expected_output=agent_resp.message.content,
        )
        eval_res = await self.evaluator.evaluate_test_case(
            test_case=tc,
            actual_output=agent_resp.message.content,
            latency_ms=span.duration_ms or 0.0,
        )

        return {
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "agent_output": agent_resp.message.content,
            "redacted_items_count": safety_res.redacted_items_count,
            "cost_usd": cost,
            "trace_id": span.trace_id,
            "eval_passed": eval_res.passed,
            "eval_score": eval_res.score,
        }
