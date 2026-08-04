import pytest

from src.adapters.mock_adapter import MockAdapter
from src.config import RetryConfig
from src.domain.exceptions import ProviderUnavailable, RouterException
from src.domain.models import CompletionRequest, CompletionResponse, FinishReason, Message, Role, TokenUsage
from src.domain.router import RoutingStrategy
from src.orchestrator.circuit_breaker import CircuitState
from src.orchestrator.pipeline import LLMOrchestrator
from src.orchestrator.router import DynamicProviderRouter


def _make_orchestrator(mock_adapter: MockAdapter) -> LLMOrchestrator:
    return LLMOrchestrator(
        providers={"mock": mock_adapter},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=0, initial_delay_seconds=0.001, jitter=False),
    )


@pytest.mark.asyncio
async def test_dynamic_router_priority_fallback():
    # Primary fails with 503 ProviderUnavailable
    def _raise_503():
        raise ProviderUnavailable(provider="primary", status_code=503)

    primary_mock = MockAdapter(failure_script=[_raise_503])
    secondary_resp = CompletionResponse(
        content="Secondary fallback response",
        token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="secondary",
        model="mock-model",
        request_id="sec-1",
    )
    secondary_mock = MockAdapter(scripted_responses=[secondary_resp])

    orch_primary = _make_orchestrator(primary_mock)
    orch_secondary = _make_orchestrator(secondary_mock)

    router = DynamicProviderRouter(
        providers={"primary": orch_primary, "secondary": orch_secondary},
        provider_priority=["primary", "secondary"],
        strategy=RoutingStrategy.PRIORITY_FALLBACK,
    )

    req = CompletionRequest(
        messages=[Message(role=Role.USER, content="Hello")],
        model="mock-model",
    )

    resp = await router.route_completion(req)
    assert resp.content == "Secondary fallback response"
    assert resp.provider == "secondary"


@pytest.mark.asyncio
async def test_dynamic_router_circuit_breaker_open_skips_provider():
    primary_mock = MockAdapter()
    secondary_resp = CompletionResponse(
        content="Bypassed open circuit primary",
        token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        latency_ms=2.0,
        finish_reason=FinishReason.STOP,
        provider="secondary",
        model="mock-model",
        request_id="sec-2",
    )
    secondary_mock = MockAdapter(scripted_responses=[secondary_resp])

    orch_primary = _make_orchestrator(primary_mock)
    # Manually trip primary circuit breaker to OPEN state
    orch_primary.get_circuit_breaker("mock").state = CircuitState.OPEN
    orch_primary.get_circuit_breaker("mock").last_failure_time = 9999999999.0

    orch_secondary = _make_orchestrator(secondary_mock)

    router = DynamicProviderRouter(
        providers={"primary": orch_primary, "secondary": orch_secondary},
        provider_priority=["primary", "secondary"],
    )

    req = CompletionRequest(messages=[Message(role=Role.USER, content="Test")], model="mock-model")
    resp = await router.route_completion(req)

    assert resp.content == "Bypassed open circuit primary"
    assert primary_mock.call_count == 0  # Primary was skipped without call


@pytest.mark.asyncio
async def test_dynamic_router_all_failed_raises():
    def _fail():
        raise ProviderUnavailable(provider="mock", status_code=500)

    orch1 = _make_orchestrator(MockAdapter(failure_script=[_fail]))
    orch2 = _make_orchestrator(MockAdapter(failure_script=[_fail]))

    router = DynamicProviderRouter(
        providers={"p1": orch1, "p2": orch2},
    )

    req = CompletionRequest(messages=[Message(role=Role.USER, content="Fail test")], model="mock-model")
    with pytest.raises(RouterException, match="All candidate providers.*failed"):
        await router.route_completion(req)
