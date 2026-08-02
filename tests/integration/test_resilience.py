import pytest

from src.adapters.mock_adapter import MockAdapter, rate_limit_failure, server_error_failure
from src.config import RetryConfig
from src.domain.exceptions import InvalidRequestError, RetryBudgetExhausted
from src.domain.models import CompletionRequest, Message, Role
from src.orchestrator.pipeline import LLMOrchestrator


def make_orchestrator(adapter: MockAdapter, max_retries: int = 3) -> LLMOrchestrator:
    recorded_sleeps: list[float] = []

    async def fast_sleep(seconds: float) -> None:
        recorded_sleeps.append(seconds)  # no real wait -- keeps the test fast & deterministic

    orch = LLMOrchestrator(
        providers={"mock": adapter},
        default_provider="mock",
        retry_config=RetryConfig(max_retries=max_retries, initial_delay_seconds=0.01, jitter=False),
        sleep_fn=fast_sleep,
    )
    orch._test_recorded_sleeps = recorded_sleeps  # type: ignore[attr-defined]
    return orch


@pytest.mark.asyncio
async def test_recovers_from_two_transient_rate_limits_then_succeeds():
    adapter = MockAdapter(failure_script=[rate_limit_failure(), rate_limit_failure(), None])
    orchestrator = make_orchestrator(adapter, max_retries=3)
    request = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    response = await orchestrator.complete(request)

    assert response.content == "mock completion"
    assert adapter.call_count == 3
    # Two retries happened -> two backoff sleeps recorded, growing (or equal, capped) each time.
    assert len(orchestrator._test_recorded_sleeps) == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_recovers_from_mixed_rate_limit_and_5xx_failures():
    adapter = MockAdapter(failure_script=[rate_limit_failure(), server_error_failure(503), None])
    orchestrator = make_orchestrator(adapter, max_retries=3)
    request = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    response = await orchestrator.complete(request)
    assert response.content == "mock completion"
    assert adapter.call_count == 3


@pytest.mark.asyncio
async def test_exhausts_retry_budget_and_raises_with_last_error_attached():
    adapter = MockAdapter(failure_script=[rate_limit_failure(), rate_limit_failure(), rate_limit_failure(), rate_limit_failure()])
    orchestrator = make_orchestrator(adapter, max_retries=2)  # allows 3 total attempts
    request = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    with pytest.raises(RetryBudgetExhausted) as excinfo:
        await orchestrator.complete(request)

    assert adapter.call_count == 3  # 1 initial + 2 retries, then gives up
    assert excinfo.value.attempts == 3
    assert excinfo.value.last_error is not None


@pytest.mark.asyncio
async def test_invalid_request_error_is_never_retried():
    def bad_request():
        raise InvalidRequestError(provider="mock", status_code=400)

    adapter = MockAdapter(failure_script=[bad_request, None])
    orchestrator = make_orchestrator(adapter, max_retries=3)
    request = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    with pytest.raises(RetryBudgetExhausted):
        await orchestrator.complete(request)

    # Only 1 call made -- non-retryable errors must not consume the retry budget.
    assert adapter.call_count == 1
    assert len(orchestrator._test_recorded_sleeps) == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_streaming_retries_connection_failure_before_first_chunk():
    adapter = MockAdapter(failure_script=[rate_limit_failure(), None], response_content="a b")
    orchestrator = make_orchestrator(adapter, max_retries=2)
    request = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    chunks = [c async for c in orchestrator.stream(request)]
    assert "".join(c.delta for c in chunks) == "a b"
    assert adapter.call_count == 2
