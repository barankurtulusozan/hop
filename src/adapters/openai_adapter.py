"""
OpenAI (and OpenAI-compatible) adapter.

This is the ONLY file in the codebase allowed to import the `openai` package.
Every vendor exception is caught here and translated into the domain
exception hierarchy before it can propagate to the orchestrator.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncIterable

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError as OpenAIRateLimitError

from src.config import ProviderCredentials
from src.domain.exceptions import InvalidRequestError, ProviderUnavailable, RateLimitExceeded
from src.domain.interfaces import LLMProvider
from src.domain.models import (
    CompletionRequest,
    CompletionResponse,
    FinishReason,
    StreamChunk,
    TokenUsage,
)

_FINISH_REASON_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
}


class OpenAIAdapter(LLMProvider):
    name = "openai"

    def __init__(self, credentials: ProviderCredentials):
        # `reveal()` is called exactly once, right here, to hand the raw key
        # to the vendor SDK's own transport layer. It is never stored,
        # logged, or passed through domain code again.
        self._client = AsyncOpenAI(
            api_key=credentials.reveal(),
            organization=credentials.organization_id,
            base_url=credentials.base_url,
        )

    def _to_openai_messages(self, request: CompletionRequest) -> list[dict]:
        return [{"role": m.role.value, "content": m.content} for m in request.messages]

    def _translate_error(self, exc: Exception) -> Exception:
        if isinstance(exc, OpenAIRateLimitError):
            retry_after = None
            headers = getattr(exc, "response", None)
            if headers is not None:
                header_val = headers.headers.get("retry-after") if hasattr(headers, "headers") else None
                if header_val:
                    try:
                        retry_after = float(header_val)
                    except ValueError:
                        retry_after = None
            return RateLimitExceeded(str(exc), provider=self.name, retry_after_seconds=retry_after)
        if isinstance(exc, APIConnectionError):
            return ProviderUnavailable(str(exc), provider=self.name)
        if isinstance(exc, APIStatusError):
            if exc.status_code >= 500:
                return ProviderUnavailable(str(exc), provider=self.name, status_code=exc.status_code)
            return InvalidRequestError(str(exc), provider=self.name, status_code=exc.status_code)
        return ProviderUnavailable(f"Unexpected OpenAI adapter failure: {exc}", provider=self.name)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start = time.perf_counter()
        try:
            resp = await self._client.chat.completions.create(
                model=request.model,
                messages=self._to_openai_messages(request),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=request.stop_sequences or None,
            )
        except Exception as exc:  # noqa: BLE001 -- intentionally broad, translated below
            raise self._translate_error(exc) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        choice = resp.choices[0]
        usage = resp.usage
        return CompletionResponse(
            content=choice.message.content or "",
            token_usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            ),
            latency_ms=latency_ms,
            finish_reason=_FINISH_REASON_MAP.get(choice.finish_reason, FinishReason.STOP),
            provider=self.name,
            model=resp.model,
            request_id=resp.id or str(uuid.uuid4()),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        try:
            stream = await self._client.chat.completions.create(
                model=request.model,
                messages=self._to_openai_messages(request),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=request.stop_sequences or None,
                stream=True,
                stream_options={"include_usage": True},
            )
            accumulated_usage: TokenUsage | None = None
            async for chunk in stream:
                if getattr(chunk, "usage", None) is not None and chunk.usage:
                    accumulated_usage = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens or 0,
                        completion_tokens=chunk.usage.completion_tokens or 0,
                    )
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                delta = choice.delta.content or ""
                is_final = choice.finish_reason is not None
                yield StreamChunk(
                    delta=delta,
                    is_final=is_final,
                    finish_reason=_FINISH_REASON_MAP.get(choice.finish_reason, None) if is_final else None,
                    token_usage=accumulated_usage if is_final else None,
                )
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc
