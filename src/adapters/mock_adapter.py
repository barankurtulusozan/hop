"""
Deterministic mock provider. No network calls. Used for unit tests and for
integration tests that need to simulate specific failure sequences
(rate limits, transient 5xx) without hitting a real vendor API.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncIterable, Callable

from src.domain.exceptions import ProviderUnavailable, RateLimitExceeded
from src.domain.interfaces import LLMProvider
from src.domain.models import (
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    StreamChunk,
    TokenUsage,
)


class MockAdapter(LLMProvider):
    name = "mock"

    def __init__(
        self,
        failure_script: list[Callable[[], None] | None] | None = None,
        response_content: str = "mock completion",
        latency_ms: float = 5.0,
        scripted_responses: list[CompletionResponse] | None = None,
    ):
        self._script = list(failure_script or [])
        self._response_content = response_content
        self._latency_ms = latency_ms
        self._scripted_responses = list(scripted_responses or [])
        self.call_count = 0

    def _consume_script(self) -> None:
        self.call_count += 1
        if self._script:
            outcome = self._script.pop(0)
            if outcome is not None:
                outcome()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start = time.perf_counter()
        self._consume_script()
        elapsed_ms = (time.perf_counter() - start) * 1000 + self._latency_ms

        if self._scripted_responses:
            return self._scripted_responses.pop(0)

        return CompletionResponse(
            content=self._response_content,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            latency_ms=elapsed_ms,
            finish_reason=FinishReason.STOP,
            provider=self.name,
            model=request.model,
            request_id=str(uuid.uuid4()),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        self._consume_script()
        words = self._response_content.split()
        for i, word in enumerate(words):
            is_final = i == len(words) - 1
            yield StreamChunk(
                delta=word + (" " if not is_final else ""),
                is_final=is_final,
                finish_reason=FinishReason.STOP if is_final else None,
                token_usage=TokenUsage(prompt_tokens=10, completion_tokens=len(words)) if is_final else None,
            )


def rate_limit_failure(retry_after: float = 0.01) -> Callable[[], None]:
    def _raise():
        raise RateLimitExceeded(provider="mock", retry_after_seconds=retry_after)
    return _raise


def server_error_failure(status_code: int = 503) -> Callable[[], None]:
    def _raise():
        raise ProviderUnavailable(provider="mock", status_code=status_code)
    return _raise
