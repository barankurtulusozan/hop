import asyncio
import json
import logging
import pytest
from src.adapters.mock_adapter import MockAdapter, server_error_failure
from src.adapters.anthropic_adapter import AnthropicAdapter
from src.config import ProviderCredentials, RetryConfig
from src.domain.exceptions import ProviderUnavailable, RateLimitExceeded, RetryBudgetExhausted
from src.domain.models import CompletionRequest, Message, Role
from src.orchestrator.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from src.orchestrator.pipeline import JsonFormatter, LLMOrchestrator
from anthropic import RateLimitError as AnthropicRateLimitError
from pydantic import SecretStr


def make_orchestrator(adapter: MockAdapter, max_retries: int = 2, failure_threshold: int = 2, timeout: float = 5.0) -> LLMOrchestrator:
    async def fast_sleep(seconds: float) -> None:
        pass

    return LLMOrchestrator(
        providers={"mock": adapter},
        default_provider="mock",
        retry_config=RetryConfig(
            max_retries=max_retries,
            initial_delay_seconds=0.001,
            jitter=False,
            request_timeout_seconds=timeout,
            circuit_breaker_failure_threshold=failure_threshold,
            circuit_breaker_recovery_time_seconds=10.0,
        ),
        sleep_fn=fast_sleep,
    )


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures_and_fast_fails():
    adapter = MockAdapter(failure_script=[server_error_failure(), server_error_failure()])
    orch = make_orchestrator(adapter, max_retries=0, failure_threshold=2)
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    # 1st attempt fails -> recorded failure 1 -> raises RetryBudgetExhausted
    with pytest.raises(RetryBudgetExhausted) as exc1:
        await orch.complete(req)
    assert isinstance(exc1.value.last_error, ProviderUnavailable)

    # 2nd attempt fails -> recorded failure 2 -> circuit breaker transitions to OPEN
    with pytest.raises(RetryBudgetExhausted) as exc2:
        await orch.complete(req)
    assert isinstance(exc2.value.last_error, ProviderUnavailable)

    cb = orch.get_circuit_breaker("mock")
    assert cb.state == CircuitState.OPEN

    # 3rd attempt fast fails immediately with CircuitBreakerOpenError without hitting adapter
    with pytest.raises(CircuitBreakerOpenError):
        await orch.complete(req)

    assert adapter.call_count == 2


@pytest.mark.asyncio
async def test_request_timeout_triggers_provider_unavailable():
    class SlowAdapter(MockAdapter):
        async def complete(self, request: CompletionRequest):
            await asyncio.sleep(0.5)
            return await super().complete(request)

    adapter = SlowAdapter()
    orch = make_orchestrator(adapter, max_retries=0, timeout=0.05)
    req = CompletionRequest(messages=[Message(role=Role.USER, content="hi")], model="mock-model")

    with pytest.raises(RetryBudgetExhausted) as exc_info:
        await orch.complete(req)

    assert exc_info.value.last_error is not None
    assert "timed out" in str(exc_info.value.last_error)
    assert getattr(exc_info.value.last_error, "status_code", None) == 504


def test_json_formatter_produces_valid_json_log_line():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="llm_request_attempt",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.provider = "openai"
    record.duration_ms = 42.5

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["logger"] == "test_logger"
    assert parsed["event"] == "llm_request_attempt"
    assert parsed["request_id"] == "req-123"
    assert parsed["provider"] == "openai"
    assert parsed["duration_ms"] == 42.5


def test_anthropic_adapter_parses_retry_after_header():
    creds = ProviderCredentials(api_key=SecretStr("test-key"))
    adapter = AnthropicAdapter(creds)

    class FakeHeaders:
        def get(self, key, default=None):
            if key.lower() == "retry-after":
                return "12.5"
            return default

    class FakeResponse:
        status_code = 429
        headers = FakeHeaders()
        request = object()

    fake_exc = AnthropicRateLimitError(
        message="rate limited",
        response=FakeResponse(),  # type: ignore
        body=None,
    )

    translated = adapter._translate_error(fake_exc)
    assert isinstance(translated, RateLimitExceeded)
    assert translated.retry_after_seconds == 12.5
