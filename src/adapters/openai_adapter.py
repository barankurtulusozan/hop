"""
OpenAI (and OpenAI-compatible) adapter.

This is the ONLY file in the codebase allowed to import the `openai` package.
Every vendor exception is caught here and translated into the domain
exception hierarchy before it can propagate to the orchestrator.
"""

from __future__ import annotations

import json
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
    Role,
    StreamChunk,
    TokenUsage,
)
from src.domain.tools import ToolCall

_FINISH_REASON_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_CALLS,
}


class OpenAIAdapter(LLMProvider):
    name = "openai"

    def __init__(self, credentials: ProviderCredentials):
        self._client = AsyncOpenAI(
            api_key=credentials.reveal(),
            organization=credentials.organization_id,
            base_url=credentials.base_url,
        )

    def _to_openai_messages(self, request: CompletionRequest) -> list[dict]:
        formatted = []
        for m in request.messages:
            if m.role == Role.TOOL:
                formatted.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content,
                })
            elif m.role == Role.ASSISTANT and m.tool_calls:
                msg = {"role": "assistant", "content": m.content or None}
                msg["tool_calls"] = [
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in m.tool_calls
                ]
                formatted.append(msg)
            else:
                formatted.append({"role": m.role.value, "content": m.content})
        return formatted

    def _to_openai_tools(self, request: CompletionRequest) -> list[dict] | None:
        if not request.tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                },
            }
            for t in request.tools
        ]

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
        kwargs = {
            "model": request.model,
            "messages": self._to_openai_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stop": request.stop_sequences or None,
        }
        tools_payload = self._to_openai_tools(request)
        if tools_payload:
            kwargs["tools"] = tools_payload

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        choice = resp.choices[0]
        usage = resp.usage

        extracted_tool_calls: list[ToolCall] = []
        if getattr(choice.message, "tool_calls", None):
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                extracted_tool_calls.append(
                    ToolCall(call_id=tc.id, tool_name=tc.function.name, arguments=args)
                )

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
            tool_calls=extracted_tool_calls,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        kwargs = {
            "model": request.model,
            "messages": self._to_openai_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stop": request.stop_sequences or None,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        tools_payload = self._to_openai_tools(request)
        if tools_payload:
            kwargs["tools"] = tools_payload

        try:
            stream = await self._client.chat.completions.create(**kwargs)
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
