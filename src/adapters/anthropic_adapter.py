"""
Anthropic adapter. Only file allowed to import the `anthropic` package.
Same translate-at-the-boundary contract as the OpenAI adapter.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncIterable

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from anthropic import RateLimitError as AnthropicRateLimitError

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
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "tool_use": FinishReason.TOOL_CALLS,
}


class AnthropicAdapter(LLMProvider):
    name = "anthropic"

    def __init__(self, credentials: ProviderCredentials):
        self._client = AsyncAnthropic(
            api_key=credentials.reveal(),
            base_url=credentials.base_url,
        )

    def _split_system(self, request: CompletionRequest) -> tuple[str | None, list[dict]]:
        """Anthropic takes `system` as a top-level field, not a message role."""
        system_parts = [m.content for m in request.messages if m.role == Role.SYSTEM]
        turns = []
        for m in request.messages:
            if m.role == Role.SYSTEM:
                continue
            if m.role == Role.TOOL:
                turns.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": m.content,
                        }
                    ],
                })
            elif m.role == Role.ASSISTANT and m.tool_calls:
                content_blocks = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.call_id,
                        "name": tc.tool_name,
                        "input": tc.arguments,
                    })
                turns.append({"role": "assistant", "content": content_blocks})
            else:
                turns.append({"role": m.role.value, "content": m.content})

        system = "\n".join(system_parts) if system_parts else None
        return system, turns

    def _to_anthropic_tools(self, request: CompletionRequest) -> list[dict] | None:
        if not request.tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters_schema,
            }
            for t in request.tools
        ]

    def _translate_error(self, exc: Exception) -> Exception:
        if isinstance(exc, AnthropicRateLimitError):
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
        return ProviderUnavailable(f"Unexpected Anthropic adapter failure: {exc}", provider=self.name)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start = time.perf_counter()
        system, turns = self._split_system(request)
        kwargs = {
            "model": request.model,
            "system": system,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stop_sequences": request.stop_sequences or None,
        }
        tools_payload = self._to_anthropic_tools(request)
        if tools_payload:
            kwargs["tools"] = tools_payload

        try:
            resp = await self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")

        extracted_tool_calls: list[ToolCall] = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                extracted_tool_calls.append(
                    ToolCall(call_id=block.id, tool_name=block.name, arguments=block.input or {})
                )

        return CompletionResponse(
            content=text,
            token_usage=TokenUsage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
            ),
            latency_ms=latency_ms,
            finish_reason=_FINISH_REASON_MAP.get(resp.stop_reason, FinishReason.STOP),
            provider=self.name,
            model=resp.model,
            request_id=resp.id or str(uuid.uuid4()),
            tool_calls=extracted_tool_calls,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterable[StreamChunk]:
        system, turns = self._split_system(request)
        kwargs = {
            "model": request.model,
            "system": system,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stop_sequences": request.stop_sequences or None,
        }
        tools_payload = self._to_anthropic_tools(request)
        if tools_payload:
            kwargs["tools"] = tools_payload

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and getattr(event.delta, "text", None):
                        yield StreamChunk(delta=event.delta.text, is_final=False)
                    elif event.type == "message_stop":
                        final_msg = await stream.get_final_message()
                        yield StreamChunk(
                            delta="",
                            is_final=True,
                            finish_reason=_FINISH_REASON_MAP.get(final_msg.stop_reason, FinishReason.STOP),
                            token_usage=TokenUsage(
                                prompt_tokens=final_msg.usage.input_tokens,
                                completion_tokens=final_msg.usage.output_tokens,
                            ),
                        )
        except Exception as exc:  # noqa: BLE001
            raise self._translate_error(exc) from exc
