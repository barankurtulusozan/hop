"""
Orchestrator: the only place business code talks to. Wraps a set of
LLMProvider adapters with retry/backoff, structured telemetry, and routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from typing import AsyncIterable, Callable

from src.config import RetryConfig
from src.domain.exceptions import LLMException, ProviderUnavailable, RetryBudgetExhausted
from src.domain.interfaces import LLMProvider
from src.domain.models import CompletionRequest, CompletionResponse, StreamChunk
from src.orchestrator.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class JsonFormatter(logging.Formatter):
    """Formats stdlib log records into valid JSON lines for log aggregators (Datadog/CloudWatch)."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        extra_fields = [
            "request_id", "provider", "model", "attempt", "outcome",
            "duration_ms", "prompt_tokens", "completion_tokens", "error",
        ]
        for field in extra_fields:
            val = getattr(record, field, None)
            if val is not None:
                log_data[field] = val
        return json.dumps(log_data)


logger = logging.getLogger("llm_orchestrator")

# Ensure logger has JSON formatter attached by default if no handlers present
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(JsonFormatter())
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def compute_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """
    Exponential backoff with full jitter, per the AWS Architecture Blog
    algorithm: sleep = random_between(0, min(max_delay, base * multiplier^attempt))

    `attempt` is 0-indexed (0 = delay before the first retry).
    """
    capped = min(config.max_delay_seconds, config.initial_delay_seconds * (config.backoff_multiplier ** attempt))
    if not config.jitter:
        return capped
    return random.uniform(0, capped)


class LLMOrchestrator:
    """
    Provider-agnostic execution orchestrator.

    - Routes requests to the configured provider (or an explicit override).
    - Retries transient failures (RateLimitExceeded, ProviderUnavailable)
      with exponential backoff + full jitter, up to `retry_config.max_retries`.
    - Enforces per-provider Circuit Breaker to prevent failure cascades.
    - Enforces per-request timeout protection.
    - Emits structured JSON log lines per attempt and summary.
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider],
        default_provider: str,
        retry_config: RetryConfig,
        sleep_fn=asyncio.sleep,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        if default_provider not in providers:
            raise ValueError(f"default_provider {default_provider!r} not present in providers: {list(providers)}")
        self._providers = providers
        self._default_provider = default_provider
        self._retry_config = retry_config
        self._sleep = sleep_fn
        self._time_fn = time_fn

        # Per-provider circuit breakers
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            name: CircuitBreaker(
                provider_name=name,
                failure_threshold=retry_config.circuit_breaker_failure_threshold,
                recovery_time_seconds=retry_config.circuit_breaker_recovery_time_seconds,
                time_fn=time_fn,
            )
            for name in providers
        }

    def _resolve_provider(self, provider_name: str | None) -> LLMProvider:
        name = provider_name or self._default_provider
        if name not in self._providers:
            raise ValueError(f"Unknown provider {name!r}. Configured providers: {list(self._providers)}")
        return self._providers[name]

    def get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        return self._circuit_breakers[provider_name]

    def _log_attempt(self, *, request_id: str, provider: str, model: str, attempt: int,
                      outcome: str, duration_ms: float, prompt_tokens: int = 0,
                      completion_tokens: int = 0, error: str | None = None) -> None:
        logger.info(
            "llm_request_attempt",
            extra={
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "attempt": attempt,
                "outcome": outcome,
                "duration_ms": round(duration_ms, 2),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "error": error,
            },
        )

    async def complete(self, request: CompletionRequest, *, provider_name: str | None = None) -> CompletionResponse:
        provider = self._resolve_provider(provider_name)
        circuit_breaker = self.get_circuit_breaker(provider.name)
        request_id = str(uuid.uuid4())
        last_error: LLMException | None = None

        for attempt in range(self._retry_config.max_retries + 1):
            if not circuit_breaker.can_execute():
                cb_err = CircuitBreakerOpenError(provider=provider.name)
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="circuit_breaker_open", duration_ms=0.0, error=cb_err.message,
                )
                raise cb_err

            start = time.perf_counter()
            try:
                async with asyncio.timeout(self._retry_config.request_timeout_seconds):
                    response = await provider.complete(request)
            except TimeoutError as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                timeout_err = ProviderUnavailable(
                    f"Request timed out after {self._retry_config.request_timeout_seconds}s",
                    provider=provider.name,
                    status_code=504,
                )
                circuit_breaker.record_failure()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="timeout", duration_ms=duration_ms, error=timeout_err.message,
                )
                last_error = timeout_err
                if attempt >= self._retry_config.max_retries:
                    break
                delay = compute_backoff_delay(attempt, self._retry_config)
                await self._sleep(delay)
                continue
            except LLMException as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                circuit_breaker.record_failure()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="error", duration_ms=duration_ms, error=exc.message,
                )
                last_error = exc
                if not exc.retryable or attempt >= self._retry_config.max_retries:
                    break
                delay = compute_backoff_delay(attempt, self._retry_config)
                await self._sleep(delay)
                continue
            else:
                duration_ms = (time.perf_counter() - start) * 1000
                circuit_breaker.record_success()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="success", duration_ms=duration_ms,
                    prompt_tokens=response.token_usage.prompt_tokens,
                    completion_tokens=response.token_usage.completion_tokens,
                )
                return response

        raise RetryBudgetExhausted(
            f"Exhausted retries for provider={provider.name} model={request.model}",
            provider=provider.name,
            attempts=self._retry_config.max_retries + 1,
            last_error=last_error,
        )

    async def stream(self, request: CompletionRequest, *, provider_name: str | None = None) -> AsyncIterable[StreamChunk]:
        """
        Streaming does not retry mid-stream (partial output can't be safely
        replayed to a caller that's already rendering tokens). It retries
        only the *connection* -- if the provider raises before yielding any
        chunk. Once the first chunk is yielded, failures propagate directly.
        """
        provider = self._resolve_provider(provider_name)
        circuit_breaker = self.get_circuit_breaker(provider.name)
        request_id = str(uuid.uuid4())
        last_error: LLMException | None = None

        for attempt in range(self._retry_config.max_retries + 1):
            if not circuit_breaker.can_execute():
                cb_err = CircuitBreakerOpenError(provider=provider.name)
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="circuit_breaker_open", duration_ms=0.0, error=cb_err.message,
                )
                raise cb_err

            started_yielding = False
            try:
                async with asyncio.timeout(self._retry_config.request_timeout_seconds):
                    async for chunk in provider.stream(request):
                        started_yielding = True
                        yield chunk
                circuit_breaker.record_success()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="success", duration_ms=0.0,
                )
                return
            except TimeoutError:
                timeout_err = ProviderUnavailable(
                    f"Streaming request timed out after {self._retry_config.request_timeout_seconds}s",
                    provider=provider.name,
                    status_code=504,
                )
                circuit_breaker.record_failure()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="timeout", duration_ms=0.0, error=timeout_err.message,
                )
                last_error = timeout_err
                if started_yielding or attempt >= self._retry_config.max_retries:
                    raise timeout_err
                delay = compute_backoff_delay(attempt, self._retry_config)
                await self._sleep(delay)
                continue
            except LLMException as exc:
                circuit_breaker.record_failure()
                self._log_attempt(
                    request_id=request_id, provider=provider.name, model=request.model,
                    attempt=attempt, outcome="error", duration_ms=0.0, error=exc.message,
                )
                last_error = exc
                if started_yielding or not exc.retryable or attempt >= self._retry_config.max_retries:
                    raise
                delay = compute_backoff_delay(attempt, self._retry_config)
                await self._sleep(delay)
                continue

        raise RetryBudgetExhausted(
            f"Exhausted retries for provider={provider.name} model={request.model}",
            provider=provider.name,
            attempts=self._retry_config.max_retries + 1,
            last_error=last_error,
        )

